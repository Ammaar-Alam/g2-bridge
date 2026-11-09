"""Probe an untested goggles model over the PC USB route, one step at a time.

Each step runs only when requested, and every USB exchange goes to a JSON Lines log:

1. Descriptors (always): list DJI USB devices, their vendor interfaces, and whether
   interface 4 matches the control interface. Reads descriptors only.
2. Identity (default): claim the control interface, exchange heartbeats, and read
   the identity reply. These are the same read-only requests DJI Assistant sends.
   Then read the firmware manifest (00/4f to <type>/5) to record the firmware and
   module versions. That read is also read-only; --no-firmware skips it.
3. Simulator mode (--simulator): send 0b/1a and record the goggles' status.
4. Test video (--test-video, needs --simulator): after a success reply, send the
   synthetic test picture at 30 fps until the run ends. The picture matches the
   model's size: 1920x1080 for Goggles 2, 1440x810 for FPV Goggles V2.

Two follow-up checks run after identity, without the regular simulator step:

- Route scan (--scan): send the identity request to IDs 0-7 of each scanned DUML
  type (default 28 and 14), then simulator mode to each module that answered,
  except CPLD <type>/3 and upgrade <type>/5. Every reply with a matching sequence
  is recorded, whatever its sender.
- Forced video (--force-video): send the test picture without a simulator
  acknowledgement. Video packets request no acknowledgement either.

For goggles whose identity matches no known code, --assume-model picks the
profile (picture size and video destination). --control-type sends heartbeats,
identity and simulator mode to another DUML device type; --video-format v2 sends
the mobile app's V2 envelope instead of the PC route's V1 packets.

Close DJI Assistant and any other bridge before running it.
"""
import argparse
from datetime import datetime
import glob
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from goggles_bridge import models
from goggles_bridge.control import V1Packet, V1Stream
from goggles_bridge.firmware import ManifestReader
from goggles_bridge.pc_video import PcVideoPacketizer
from goggles_bridge.protocol import Address, VideoPacketizer, VideoProfile
from goggles_bridge.session import ControlSession, SessionError, MODELS, EXPERIMENTAL_MODELS
from goggles_bridge.usb_transport import DEFAULT_DLL, select_control_link
from goggles_bridge.serial_transport import ControlSerial, list_dji_ports

TEST_FRAMES = {
    (1920, 1080): (ROOT / 'docs/research/evidence/synthetic-frame.h264',
                   '8b2e9ea7d0189631306e1659227abd94034ea96148f26ec8d2855962992d6735'),
    (1440, 810): (ROOT / 'docs/research/evidence/synthetic-frame-1440x810.h264',
                  'f99c6e7668ed4a48e8de04aee570a9d3580d9277e26efb767b8650d1112ef33a'),
}
# Mobile-app V2 profiles by model name; the PC route is V1 by default
NATIVE_PROFILES = {'DJI Goggles 2': 'zv900', 'DJI Goggles Integra': 'zv900', 'DJI Goggles 3': 'zv900',
                   'DJI FPV Goggles V2': 'pigeon', 'DJI FPV Goggles V1': 'pigeon'}
TEST_VIDEO_FPS = 30  # default; --test-fps overrides
SCAN_WAIT = .6
SCAN_SKIP_SIMULATOR = {3, 5}  # CPLD and upgrade modules
DEFAULT_SCAN_TYPES = (28, 14)
# libusb speed codes
SPEEDS = {1: 'low', 2: 'full', 3: 'high', 4: 'super', 5: 'super-plus'}


def _descriptor_parser():
    spec = importlib.util.spec_from_file_location('usb_descriptors', ROOT / 'scripts/read_usb_descriptors.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_configuration


def sysfs_configuration(descriptors):
    """Return the first configuration descriptor from a Linux sysfs descriptors file."""
    if len(descriptors) < 18 + 9 or descriptors[:2] != b'\x12\x01':
        raise ValueError('Unexpected sysfs descriptor layout')
    total = int.from_bytes(descriptors[18+2:18+4], 'little')
    config = descriptors[18:18+total]
    if len(config) != total:
        raise ValueError('Truncated sysfs configuration descriptor')
    return config


def read_configuration(device):
    """Read raw configuration bytes; Linux sysfs needs no device permissions."""
    if sys.platform.startswith('linux'):
        for path in glob.glob('/sys/bus/usb/devices/*/'):
            try:
                bus = int(Path(path, 'busnum').read_text())
                address = int(Path(path, 'devnum').read_text())
            except (OSError, ValueError):
                continue
            if (bus, address) == (device.bus, device.address):
                return sysfs_configuration(Path(path, 'descriptors').read_bytes()), 'sysfs'
    header = bytes(device.ctrl_transfer(0x80, 6, 0x0200, 0, 9))
    total = int.from_bytes(header[2:4], 'little')
    return bytes(device.ctrl_transfer(0x80, 6, 0x0200, 0, total)), 'control-transfer'


def describe_packet(packet):
    return dict(command=f'{packet.command_set:02x}/{packet.command_id:02x}',
                sender=f'{packet.sender_type}/{packet.sender_id}',
                receiver=f'{packet.receiver_type}/{packet.receiver_id}',
                sequence=packet.sequence, response=packet.is_response, payload=packet.payload.hex())


def test_frame_for(profile):
    """Return (bytes, path) of the synthetic picture matching the profile's size, verifying its hash."""
    try:
        path, digest = TEST_FRAMES[(profile.width, profile.height)]
    except KeyError:
        raise RuntimeError(f'No synthetic test picture for {profile.size}') from None
    frame = path.read_bytes()
    if hashlib.sha256(frame).hexdigest() != digest:
        raise RuntimeError(f'Unexpected test frame hash: {path}')
    return frame, path


class Log:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('x', encoding='utf-8')
        self.started = time.monotonic()

    def __call__(self, event, **fields):
        row = dict(seconds=round(time.monotonic()-self.started, 6), event=event, **fields)
        self.stream.write(json.dumps(row) + '\n')
        self.stream.flush()
        return row

    def close(self):
        self.stream.close()


def probe_descriptors(log, backend, args):
    import usb.core
    parse_configuration = _descriptor_parser()
    devices = list(usb.core.find(find_all=True, backend=backend, idVendor=0x2ca3))
    print(f'Step 1: found {len(devices)} DJI USB device(s)')
    if not devices:
        print('  Power the goggles, connect a USB data cable, and check that DJI Assistant is closed')
    product_ids = None if args.any_product else models.PRODUCT_IDS
    for device in devices:
        row = dict(vendor_id='2ca3', product_id=f'{device.idProduct:04x}', bcd_usb=f'{device.bcdUSB:04x}',
                   speed=SPEEDS.get(getattr(device, 'speed', None)), bus=device.bus, address=device.address,
                   known_product=models.PRODUCT_IDS.get(device.idProduct))
        try:
            raw, source = read_configuration(device)
            row.update(configuration_hex=raw.hex(), descriptor_source=source,
                       configuration=parse_configuration(raw))
        except (OSError, ValueError, usb.core.USBError) as exc:
            row['configuration_error'] = str(exc)
        try:
            _, link = select_control_link([device], interface=args.interface, product_ids=product_ids)
            row['control_interface'] = (f'interface {link.interface}, bulk out {link.endpoint_out:#04x}, '
                                        f'in {link.endpoint_in:#04x}, {link.packet_size}-byte packets')
        except Exception as exc:
            row['control_interface'] = f'{type(exc).__name__}: {exc}'
        log('device', **row)
        print(f"  {row['vendor_id']}:{row['product_id']} USB {row['bcd_usb']} speed={row['speed']} "
              f"({row['known_product'] or 'product not in the known list'})")
        for interface in row.get('configuration', {}).get('interfaces', []):
            if interface['usb_class'] != 0xff:
                continue
            endpoints = ', '.join(f"{e['address']}/{e['max_packet_size']}" for e in interface['endpoints'])
            print(f"  MI{interface['number']:02d} class {interface['usb_class']:02x}/{interface['subclass']:02x}/"
                  f"{interface['protocol']:02x}, endpoints {endpoints}")
        print(f"  Control interface: {row['control_interface']}")
    return devices


class RouteScan:
    """Send one request at a time and record any reply that carries its sequence."""
    def __init__(self, log, types=DEFAULT_SCAN_TYPES):
        self.log = log
        self.queue = [('identity', device_type, receiver_id) for device_type in types for receiver_id in range(8)]
        self.current = None
        self.results = []
        self.simulator_queued = False

    @property
    def done(self):
        return not self.queue and self.current is None and self.simulator_queued

    def receive(self, packet):
        if self.current and packet.is_response and packet.sequence == self.current['sequence']:
            self.current['replies'].append(describe_packet(packet))

    def poll(self, now, next_sequence, send):
        if self.current and now - self.current['sent_at'] >= SCAN_WAIT:
            row = self.current
            self.current = None
            del row['sent_at']
            self.results.append(row)
            self.log('scan', **row)
            replies = ', '.join(f"{r['sender']} status {r['payload'][:2] or 'none'}" for r in row['replies'])
            print(f"  {row['request']} -> {row['receiver_type']}/{row['receiver_id']}: {replies or 'no reply'}",
                  flush=True)
        if self.current or self.done:
            return
        if not self.queue:
            answered = sorted({(row['receiver_type'], row['receiver_id']) for row in self.results
                               if row['request'] == 'identity' and row['replies']})
            self.queue = [('simulator', t, i) for t, i in answered if i not in SCAN_SKIP_SIMULATOR]
            self.simulator_queued = True
            if not self.queue:
                return
        request, receiver_type, receiver_id = self.queue.pop(0)
        command, payload = ((0, 0xff), b'\0') if request == 'identity' else ((0x0b, 0x1a), bytes.fromhex('01010000'))
        sequence = next_sequence()
        send(V1Packet(*command, 10, 1, receiver_type, receiver_id, 0, 2, sequence, payload))
        self.current = dict(request=request, receiver_type=receiver_type, receiver_id=receiver_id,
                            sequence=sequence, sent_at=now, replies=[])


def report_firmware(log, reader):
    """Log and print the manifest result once, returning the summary for the result row."""
    if reader.error:
        summary = dict(error=reader.error, bytes=len(reader.data))
        print(f'  Firmware manifest: {reader.error}', flush=True)
    else:
        summary = dict(reader.manifest.as_dict(), bytes=len(reader.data), chunks=reader.chunks)
        print(f"  Firmware: {summary['firmware']} (device {summary['device']})", flush=True)
        for module in summary['modules']:
            print(f"    module {module['id']} {module['name']}: {module['version']} ({module['file']})", flush=True)
    log('firmware', **summary, container_hex=bytes(reader.data).hex())
    return summary


class VideoSender:
    """Packetize the test picture the way the bridge does (v1) or the mobile app does (v2)."""
    def __init__(self, profile, video_format, session, receiver=None, sender=None):
        self.video_format = video_format
        self.session = session
        receiver = receiver or profile.video
        if video_format == 'v1':
            self.packetizer = PcVideoPacketizer(receiver=receiver, sender=sender or (10, 1))
        else:
            self.packetizer = VideoPacketizer(NATIVE_PROFILES[profile.name])
            native = self.packetizer.profile
            self.packetizer.profile = VideoProfile(Address(receiver[0], receiver[1], native.receiver.index),
                                                   native.logiclink)

    def wire(self, frame):
        if self.video_format == 'v1':
            return b''.join(p.serialize() for p in self.packetizer.packetize(frame, self.session.reserve_sequence))
        return b''.join(self.packetizer.packetize(frame))


def probe_session(log, args):
    from goggles_bridge.usb_transport import ControlUsb
    session = ControlSession(models={**MODELS, **EXPERIMENTAL_MODELS}, enter_simulator=args.simulator,
                             assume_model=args.assume_model, control_type=args.control_type)
    target = 'ready' if args.simulator else 'identified'
    decoder = V1Stream()
    scan = RouteScan(log, args.scan_types) if args.scan else None
    firmware = None if args.no_firmware else ManifestReader(receiver=(args.control_type, 5))
    sender = None
    result = dict(state=None, identity=None, model=None, firmware=None, frames_sent=0, error=None,
                  video_format=args.video_format if frame_flag(args) else None)
    previous = None
    next_frame = None
    frame = None
    started = time.monotonic()
    product_ids = None if args.any_product else models.PRODUCT_IDS
    if args.serial:
        transport = ControlSerial(None if args.serial == 'auto' else args.serial, product_ids=product_ids)
    else:
        dll = args.libusb0_dll if args.usb_backend == 'libusb0' else args.dll
        transport = ControlUsb(dll, interface=args.interface, product_ids=product_ids, backend=args.usb_backend)
    video_link = None
    if args.video_bulk_interface is not None:
        video_link = ControlUsb(args.libusb0_dll or args.dll, interface=args.video_bulk_interface, product_ids=product_ids,
                                backend=args.usb_backend if args.usb_backend != 'auto' else 'libusb0')
        log('video_link', interface=video_link.link.interface, endpoint_out=video_link.link.endpoint_out,
            endpoint_in=video_link.link.endpoint_in)
        print(f'  Video goes to bulk interface {video_link.link.interface} (out {video_link.link.endpoint_out:#04x})')
    with transport as usb:
        if args.serial:
            log('claimed', serial_port=usb.port)
            print(f'  Opened serial port {usb.port}')
        else:
            log('claimed', interface=usb.link.interface, product_id=f'{usb.link.product_id:04x}',
                endpoint_out=usb.link.endpoint_out, endpoint_in=usb.link.endpoint_in, packet_size=usb.link.packet_size)

        def send(packet):
            data = packet.serialize()
            usb.write(data)
            log('send', hex=data.hex(), **describe_packet(packet))

        try:
            while time.monotonic()-started < args.seconds:
                for request in session.poll(time.monotonic()):
                    send(request)
                data = usb.read(timeout_ms=5 if next_frame is not None else 50)
                if data:
                    log('receive', hex=data.hex())
                for packet in decoder.feed(data):
                    log('packet', **describe_packet(packet))
                    if scan:
                        scan.receive(packet)
                    if firmware:
                        firmware.receive(packet)
                    for request in session.receive(packet, time.monotonic()):
                        send(request)
                if session.state != previous:
                    previous = session.state
                    log('state', value=session.state, identity=session.identity, model=session.model)
                    print(f'  Control state: {session.state}', flush=True)
                    if session.state == 'identity':
                        print('Step 2: heartbeat acknowledged, reading identity')
                    elif session.state in ('simulator', 'identified'):
                        assumed = ' (assumed)' if session.profile and not models.match_identity(
                            session.identity, [session.profile]) else ''
                        print(f'  Identity: {session.identity} ({session.model}{assumed}, {session.profile.size})')
                        if frame_flag(args):
                            frame, path = test_frame_for(session.profile)
                            sender = VideoSender(session.profile, args.video_format, session, args.video_receiver,
                                                 args.video_sender)
                            log('test_frame', path=str(path.relative_to(ROOT)), bytes=len(frame),
                                size=session.profile.size, video_format=args.video_format,
                                receiver='/'.join(map(str, args.video_receiver or session.profile.video)))
                        if session.state == 'simulator':
                            print(f'Step 3: sending simulator mode 0b/1a to {args.control_type}/0')
                    elif session.state == 'ready':
                        print('  Simulator mode acknowledged with status 00')
                        if frame is not None:
                            target = '/'.join(map(str, args.video_receiver or session.profile.video))
                            print(f'Step 4: sending the {session.profile.size} test picture at {TEST_VIDEO_FPS} fps '
                                  f'as {args.video_format} to {target}; watch the lenses')
                            next_frame = time.monotonic()
                if firmware and session.state in ('identified', 'simulator', 'ready'):
                    if not firmware.done:
                        for request in firmware.poll(time.monotonic(), session.reserve_sequence):
                            send(request)
                    if firmware.done and result['firmware'] is None:
                        result['firmware'] = report_firmware(log, firmware)
                if session.state == 'identified' and scan and not scan.done:
                    if not scan.results and scan.current is None:
                        print('Scan: one request at a time, waiting 0.6 s for replies')
                    scan.poll(time.monotonic(), session.reserve_sequence, send)
                if (args.force_video and session.state == 'identified' and next_frame is None
                        and (scan is None or scan.done)):
                    print(f'Forced video: sending the {session.profile.size} test picture at {TEST_VIDEO_FPS} fps '
                          f'as {args.video_format} without simulator mode; watch the lenses', flush=True)
                    next_frame = time.monotonic()
                if video_link is not None:
                    bulk_in = video_link.read(timeout_ms=1)
                    if bulk_in:
                        log('receive_bulk', hex=bulk_in.hex())
                        result['bulk_in_bytes'] = result.get('bulk_in_bytes', 0) + len(bulk_in)
                if next_frame is not None and time.monotonic() >= next_frame:
                    wire = sender.wire(frame)
                    (video_link or usb).write(wire)
                    result['frames_sent'] += 1
                    if result['frames_sent'] % args.test_fps == 1:
                        log('video', frames=result['frames_sent'], bytes=len(wire))
                    next_frame += 1/args.test_fps
        except SessionError as exc:
            result['error'] = str(exc)
            print(f'  Session ended: {exc}')
        result.update(state=session.state, identity=session.identity, model=session.model,
                      reached=session.state == target and (scan is None or scan.done),
                      discarded_bytes=decoder.discarded)
        if scan:
            result['scan'] = scan.results
    if video_link is not None:
        video_link.close()
    return result


def frame_flag(args):
    return args.test_video or args.force_video


def parse_route(text):
    try:
        device_type, device_id = (int(part) for part in text.split('/'))
    except ValueError:
        raise argparse.ArgumentTypeError('routes look like TYPE/ID, for example 28/1') from None
    if not (0 <= device_type < 32 and 0 <= device_id < 8):
        raise argparse.ArgumentTypeError('TYPE ranges 0-31 and ID 0-7')
    return (device_type, device_id)


def parse_types(text):
    try:
        types = tuple(dict.fromkeys(int(part) for part in text.split(',')))
    except ValueError:
        raise argparse.ArgumentTypeError('DUML types are comma-separated integers') from None
    if not types or any(not 0 <= t < 32 for t in types):
        raise argparse.ArgumentTypeError('DUML types range from 0 to 31')
    return types


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, help='New JSON Lines log path (default: work/probe/<time>.jsonl)')
    parser.add_argument('--dll', type=Path, default=DEFAULT_DLL, help='Windows only: verified DJI x64 libusb0_device.dll')
    parser.add_argument('--descriptors-only', action='store_true', help='Stop after step 1')
    parser.add_argument('--simulator', action='store_true', help='Step 3: send simulator mode 0b/1a after identity')
    parser.add_argument('--test-video', action='store_true', help='Step 4: send the test picture after simulator mode')
    parser.add_argument('--scan', action='store_true', help='Send identity and simulator requests to IDs 0-7 of --scan-types')
    parser.add_argument('--scan-types', type=parse_types, default=DEFAULT_SCAN_TYPES,
                        help='Comma-separated DUML device types for --scan (default: 28,14)')
    parser.add_argument('--force-video', action='store_true', help='Send the test picture without simulator mode')
    parser.add_argument('--no-firmware', action='store_true', help='Skip the read-only firmware manifest read')
    parser.add_argument('--assume-model', choices=sorted(models.BY_NAME),
                        help='Profile to use when the identity matches no known code')
    parser.add_argument('--control-type', type=int, default=28,
                        help='DUML device type for heartbeat, identity and simulator mode (default: 28)')
    parser.add_argument('--video-format', choices=('v1', 'v2'), default='v1',
                        help='v1: PC-route V1 packets (default); v2: the mobile app envelope')
    parser.add_argument('--video-sender', type=parse_route, metavar='TYPE/ID',
                        help='V1 video sender address instead of the PC (10/1), for example the mobile app 2/0')
    parser.add_argument('--test-fps', type=int, default=TEST_VIDEO_FPS, help='Test picture rate (default: 30)')
    parser.add_argument('--video-receiver', type=parse_route, metavar='TYPE/ID',
                        help='Send video to this DUML address instead of the model profile, for example 28/1')
    parser.add_argument('--usb-backend', choices=('auto', 'dji', 'libusb1', 'libusb0'), default='auto',
                        help="USB library: DJI's driver DLL (auto on Windows), libusb-1.0, or libusb-win32's libusb0.dll")
    parser.add_argument('--libusb0-dll', type=Path, help='64-bit libusb-win32 libusb0.dll for --usb-backend libusb0 '
                        '(default: the System32 copy)')
    parser.add_argument('--video-bulk-interface', type=int, metavar='N',
                        help='Send video on this bulk interface (libusb0 backend) while control stays on --serial')
    parser.add_argument('--interface', type=int, default=4, help='USB interface number to claim (default: 4)')
    parser.add_argument('--any-product', action='store_true', help='Accept any DJI product ID, not only the known ones')
    parser.add_argument('--serial', nargs='?', const='auto', metavar='PORT',
                        help="Talk over the goggles' USB virtual COM port instead of a bulk interface "
                             '(FPV Goggles V2 interface 4). Without PORT, the one DJI COM port is used')
    parser.add_argument('--seconds', type=float, default=15, help='Session length in seconds, from 5 to 300')
    args = parser.parse_args()
    if args.test_video and not args.simulator:
        parser.error('--test-video requires --simulator')
    if args.simulator and (args.scan or args.force_video):
        parser.error('--scan and --force-video replace --simulator; run them without it')
    if not 1 <= args.test_fps <= 100:
        parser.error('--test-fps ranges from 1 to 100')
    if not 5 <= args.seconds <= 300:
        parser.error('--seconds must be between 5 and 300')
    if not 0 <= args.control_type < 32:
        parser.error('--control-type ranges from 0 to 31')
    if not 0 <= args.interface < 32:
        parser.error('--interface ranges from 0 to 31')
    output = args.output or ROOT / 'work' / 'probe' / f'{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}.jsonl'
    if output.exists():
        parser.error(f'Output already exists: {output}')
    from goggles_bridge.usb_transport import get_backend
    log = Log(output)
    exit_code = 1
    try:
        log('starting', platform=sys.platform, args={k: str(v) for k, v in vars(args).items()})
        if args.serial:
            ports = list_dji_ports(None if args.any_product else models.PRODUCT_IDS)
            for port in ports:
                log('serial_port', device=port.device, description=port.description, product_id=f'{port.pid:04x}')
                print(f'Step 1: DJI serial port {port.device}: {port.description} (product {port.pid:04x})')
            devices = ports or ([args.serial] if args.serial != 'auto' else [])
            if not devices:
                print('  No DJI virtual COM port found; close DJI Assistant and check the cable')
        else:
            dll = args.libusb0_dll if args.usb_backend == 'libusb0' else args.dll
            devices = probe_descriptors(log, get_backend(dll, args.usb_backend), args)
        if devices and args.descriptors_only:
            exit_code = 0
        elif devices:
            result = probe_session(log, args)
            log('result', **result)
            print(f"Result: state={result['state']} identity={result['identity']!r} model={result['model']!r}"
                  + (f" frames_sent={result['frames_sent']}" if frame_flag(args) else ''))
            exit_code = 0 if result['reached'] else 1
    except Exception as exc:
        log('error', message=f'{type(exc).__name__}: {exc}')
        print(f'Probe stopped: {exc}', file=sys.stderr)
    finally:
        log('stopped')
        log.close()
        print(f'Log: {output}')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
