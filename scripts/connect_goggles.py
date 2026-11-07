"""Open a Goggles 2 control session for a specified duration."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goggles_bridge.control import V1Stream
from goggles_bridge.session import ControlSession
from goggles_bridge.windows_usb import DEFAULT_DLL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, default=DEFAULT_DLL, help='Verified DJI x64 libusb0_device.dll')
    parser.add_argument('--python-deps', type=Path, help='Optional local PyUSB 1.3.1 installation directory')
    parser.add_argument('--seconds', type=float, default=30, help='Session duration in seconds, from 1 to 300')
    parser.add_argument('--log', type=Path, required=True, help='Path for a new JSON Lines log (must not already exist)')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error('--seconds must be between 1 and 300')
    if args.python_deps:
        sys.path.insert(0, str(args.python_deps.resolve()))
    from goggles_bridge.windows_usb import WindowsControlUsb
    session = ControlSession()
    decoder = V1Stream()
    started = time.monotonic()
    previous = None
    with args.log.open('x', encoding='utf-8') as log:
        def record(event, **fields):
            log.write(json.dumps(dict(seconds=round(time.monotonic()-started, 6), event=event, **fields)) + '\n')
            log.flush()

        try:
            with WindowsControlUsb(args.dll) as usb:
                while time.monotonic()-started < args.seconds:
                    for request in session.poll(time.monotonic()):
                        data = request.serialize()
                        usb.write(data)
                        record('send', hex=data.hex())
                    data = usb.read(timeout_ms=50)
                    if data:
                        record('receive', hex=data.hex())
                    for packet in decoder.feed(data):
                        for request in session.receive(packet, time.monotonic()):
                            raw = request.serialize()
                            usb.write(raw)
                            record('send', hex=raw.hex())
                    if session.state != previous:
                        previous = session.state
                        print(f'Control state: {session.state}', flush=True)
                        record('state', value=session.state, identity=session.identity)
                        if session.state == 'ready':
                            print('Simulator mode acknowledged. Video is not sent by this command.', flush=True)
        except Exception as exc:
            record('error', message=str(exc))
            raise
        finally:
            record('stopped', state=session.state, discarded_bytes=decoder.discarded)


if __name__ == '__main__':
    main()
