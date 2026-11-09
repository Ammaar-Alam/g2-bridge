"""Check whether a goggles virtual COM port parses DUML V2 frames, not only V1.

Sends a V1 heartbeat (known to be answered), then V2 heartbeats and identity
requests with the mobile app's sender address and the PC's, and reports every
V1 or V2 reply. Read-only: no simulator mode, no video.

    python tools/research/serial_v2_probe.py [--port COM10] [--control-type 28]
"""
import argparse
from dataclasses import replace
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from goggles_bridge.control import V1Packet, V1Stream, heartbeat, device_info
from goggles_bridge.protocol import Address, V2Packet
from goggles_bridge.serial_transport import ControlSerial

APP = Address(2, 0, 0x0101)
PC = Address(10, 1, 0x0000)


def find_v2(data):
    """Return (packets, leftover) for any complete V2 frames in data."""
    found, i = [], 0
    while True:
        i = data.find(b'\x55\x18\x08', i)
        if i < 0 or len(data) < i + 5:
            break
        length = int.from_bytes(data[i+3:i+5], 'little')
        if 29 <= length <= len(data) - i:
            try:
                found.append(V2Packet.parse(data[i:i+length]))
                i += length
                continue
            except ValueError:
                pass
        i += 1
    return found


def exchange(usb, label, wire, seconds=1.5):
    usb.write(wire)
    data, deadline = b'', time.monotonic() + seconds
    while time.monotonic() < deadline:
        data += usb.read(timeout_ms=50)
    v1 = [p for p in V1Stream().feed(data) if p.is_response]
    v2 = [p for p in find_v2(data) if p.sender.device_type != 2]
    print(f'{label}: {len(data)} bytes back; V1 replies: '
          + (', '.join(f'{p.command_set:02x}/{p.command_id:02x} from {p.sender_type}/{p.sender_id} {p.payload.hex()[:16]}' for p in v1) or 'none')
          + '; V2 frames: ' + (', '.join(f'{p.command_set:02x}/{p.command_id:02x} from {p.sender.device_type}/{p.sender.device_id} {p.payload.hex()[:16]}' for p in v2) or 'none'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port')
    parser.add_argument('--control-type', type=int, default=28)
    args = parser.parse_args()
    t = args.control_type
    with ControlSerial(args.port) as usb:
        print(f'port {usb.port}')
        exchange(usb, f'V1 heartbeat from pc 10/1 to {t}/0', replace(heartbeat(0x100), sender_type=10, sender_id=1, receiver_type=t).serialize())
        for sender_name, sender in (('app 2/0', APP), ('pc 10/1', PC)):
            hb = V2Packet(0x00, 0x00, sender, Address(t, 0, 0x0000), 2, 0x200, bytes.fromhex('000020000000')).serialize()
            exchange(usb, f'V2 heartbeat from {sender_name} to {t}/0', hb)
            info = V2Packet(0x00, 0xff, sender, Address(t, 1, 0x0000), 2, 0x201, b'\0').serialize()
            exchange(usb, f'V2 identity from {sender_name} to {t}/1', info)
            info_idx = V2Packet(0x00, 0xff, sender, Address(t, 1, 0x0900 if t == 28 else 0x0701), 2, 0x202, b'\0').serialize()
            exchange(usb, f'V2 identity from {sender_name} to {t}/1 with index', info_idx)
        exchange(usb, 'V1 heartbeat again', replace(heartbeat(0x101), sender_type=10, sender_id=1, receiver_type=t).serialize())


if __name__ == '__main__':
    main()
