"""Read-only listen on Goggles 2 vendor bulk IN endpoints.

Claims each requested interface and reads its IN endpoint, printing any bytes the
goggles push on their own. It writes nothing to the device: no handshake, no
command, no OUT transfer. A channel that stays silent here needs the host to
address it first; that is a separate, deliberate step, not this probe.

The untested vendor channels (same ff/43/01 class as the working video channel
MI04) are the plausible place a head-orientation or telemetry stream would show
up. Run this, then move and rotate the goggles; watch for bytes that change with
motion.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from goggles_bridge.usb_transport import PRODUCT_ID, VENDOR_ID, get_backend, is_timeout

# (interface number, IN endpoint). MI04/0x85 is the known video+DUML channel; omit it.
DEFAULT_CHANNELS = ((3, 0x84), (5, 0x86), (6, 0x87), (7, 0x88))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, help='Windows only: verified DJI x64 libusb0_device.dll '
                        '(default: DJI_USB_DLL or the installed driver copy)')
    parser.add_argument('--python-deps', type=Path, help='Directory containing PyUSB')
    parser.add_argument('--seconds', type=float, default=25.0)
    parser.add_argument('--channels', help='Comma list of iface:ep_hex, e.g. 3:0x84,5:0x86')
    args = parser.parse_args()

    if args.python_deps:
        sys.path.insert(0, str(args.python_deps.resolve()))

    channels = DEFAULT_CHANNELS
    if args.channels:
        channels = tuple((int(a), int(b, 0)) for a, b in
                         (pair.split(':') for pair in args.channels.split(',')))

    backend = get_backend(args.dll)
    import usb.core as core
    import usb.util as util
    # Each MI is its own libusb-win32 node; map interface number -> owning device node.
    nodes = list(core.find(find_all=True, backend=backend, idVendor=VENDOR_ID, idProduct=PRODUCT_ID))
    iface_to_dev = {}
    for node in nodes:
        for cfg in node:
            for intf in cfg:
                iface_to_dev.setdefault(intf.bInterfaceNumber, node)
    if not nodes:
        print('No goggles found (VID 2ca3 PID 0020). Powered on and connected?')
        return 1
    print(f'{len(nodes)} node(s); interfaces visible: {sorted(iface_to_dev)}')

    claimed = []
    for interface, _ in channels:
        device = iface_to_dev.get(interface)
        if device is None:
            print(f'MI{interface:02d}: no node exposes this interface')
            continue
        try:
            util.claim_interface(device, interface)
            claimed.append(interface)
        except core.USBError as exc:
            print(f'MI{interface:02d}: cannot claim ({exc})')
    if not claimed:
        for node in nodes:
            util.dispose_resources(node)
        return 1

    labels = ', '.join(f'MI{i:02d} 0x{e:02x}' for i, e in channels if i in claimed)
    print(f'Listening (read-only, writing nothing) on {labels} for {args.seconds:.0f}s.')
    print('Move and rotate the goggles the whole time. Ctrl+C to stop early.\n')

    stats = {e: {'packets': 0, 'bytes': 0, 'first': None, 'last': None, 'errors': 0} for _, e in channels}
    end = time.monotonic() + args.seconds
    try:
        while time.monotonic() < end:
            for interface, endpoint in channels:
                if interface not in claimed:
                    continue
                try:
                    data = bytes(iface_to_dev[interface].read(endpoint, 4096, timeout=200))
                except core.USBError as exc:
                    if is_timeout(exc):
                        continue
                    stats[endpoint]['errors'] += 1
                    if stats[endpoint]['errors'] == 1:
                        print(f'MI{interface:02d} 0x{endpoint:02x}: read error ({exc})')
                    continue
                if not data:
                    continue
                s = stats[endpoint]
                s['packets'] += 1
                s['bytes'] += len(data)
                if s['first'] is None:
                    s['first'] = data
                s['last'] = data
                stamp = time.strftime('%H:%M:%S')
                print(f'[{stamp}] MI{interface:02d} 0x{endpoint:02x} {len(data):>4}B: {data[:48].hex()}')
    except KeyboardInterrupt:
        print('\n(stopped)')
    finally:
        for node in nodes:
            util.dispose_resources(node)

    print('\n--- summary ---')
    incomplete = False
    for interface, endpoint in channels:
        s = stats[endpoint]
        prefix = f'MI{interface:02d} 0x{endpoint:02x}:'
        if interface not in claimed:
            print(f'{prefix} NOT TESTED (interface unavailable)')
            incomplete = True
            continue
        if s['packets'] == 0 and s['errors']:
            print(f'{prefix} INCOMPLETE ({s["errors"]} read errors, no data; silence not established)')
            incomplete = True
            continue
        line = f'{prefix} {s["packets"]} packets, {s["bytes"]} bytes'
        if s['errors']:
            line += f', {s["errors"]} read errors'
            incomplete = True
        if s['first'] is not None:
            changed = 'changed' if s['first'] != s['last'] else 'identical'
            line += f' | first={s["first"][:24].hex()} last={s["last"][:24].hex()} ({changed})'
        print(line)
    # A failed or missing observation must not read as measured silence.
    if incomplete:
        print('\nIncomplete: at least one requested channel was not fully observed.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
