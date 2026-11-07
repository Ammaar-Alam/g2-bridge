"""Stream the Windows desktop to stock DJI Goggles 2 in Virtual Flight mode."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import signal
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from goggles_bridge.windows_usb import DEFAULT_DLL, USB_WRITE_SIZES

# winget adds this folder to PATH but terminals opened before the install miss it
WINGET_LINKS = Path(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Links')
SETUP_HINTS = {
    'dll': 'DJI USB driver not found. Install DJI Assistant 2 (Consumer Drones Series), or pass --dll',
    'ffmpeg': 'FFmpeg not found. Run "winget install Gyan.FFmpeg", or pass --ffmpeg',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, default=os.environ.get('DJI_USB_DLL') or DEFAULT_DLL,
                        help='DJI x64 libusb0_device.dll (default: DJI_USB_DLL or the installed driver copy)')
    parser.add_argument('--ffmpeg', type=Path, default=os.environ.get('GOGGLES_FFMPEG') or shutil.which('ffmpeg')
                        or shutil.which('ffmpeg', path=str(WINGET_LINKS)),
                        help='FFmpeg executable with NVENC and the chosen capture filter (default: GOGGLES_FFMPEG or PATH)')
    parser.add_argument('--python-deps', type=Path, help='Optional directory containing PyUSB 1.3.1')
    parser.add_argument('--fps', type=int, choices=(60, 100), default=100,
                        help='Target encoder frame rate (default: 100)')
    parser.add_argument('--bitrate-mbps', type=int, choices=(8, 10, 12, 16, 20, 24), default=20)
    parser.add_argument('--capture', choices=('gfxcapture', 'ddagrab'), default='gfxcapture',
                        help='Windows Graphics Capture with GPU scaling, or Desktop Duplication with CPU scaling')
    parser.add_argument('--capture-fps', type=int, default=240, help='Maximum capture rate for gfxcapture, in fps')
    parser.add_argument('--display', type=int, default=0, help='Zero-based monitor index')
    parser.add_argument('--hide-cursor', action='store_true')
    parser.add_argument('--preset', choices=('p1', 'p4'), default='p4')
    parser.add_argument('--h264-profile', choices=('baseline', 'high'), default='high',
                        help='H.264 profile (default: high)')
    parser.add_argument('--keyframe-seconds', type=int, choices=(1, 3), default=3)
    parser.add_argument('--low-latency', action=argparse.BooleanOptionalAction, default=True,
                        help='Release complete encoded frames immediately and remove H.264 filler data (default: on)')
    parser.add_argument('--usb-write-size', type=int, choices=USB_WRITE_SIZES, default=16384,
                        help='Maximum bytes per USB write (default: 16384)')
    parser.add_argument('--seconds', type=float, default=0, help='Duration in seconds, including reconnects (0 runs until stopped)')
    parser.add_argument('--no-reconnect', action='store_true', help='Exit on USB or heartbeat loss')
    parser.add_argument('--stop-file', type=Path, help='Stop if this file is created')
    parser.add_argument('--log', type=Path, help='Path for a new JSON Lines log (default: a unique file in work/logs)')
    args = parser.parse_args()
    for name in ('dll', 'ffmpeg'):
        path = getattr(args, name)
        if path is None or not path.is_file():
            parser.error(SETUP_HINTS[name] if path in (None, DEFAULT_DLL) else f'--{name} file not found: {path}')
    if args.stop_file and args.stop_file.exists():
        parser.error('--stop-file already exists; use a new path or remove the old stop marker')
    if args.python_deps:
        sys.path.insert(0, str(args.python_deps.resolve()))
    try:
        import usb
    except ImportError:
        usb = None
    if getattr(usb, '__version__', None) != '1.3.1':
        parser.error('PyUSB 1.3.1 is required. Run "python -m pip install -r requirements.txt"')
    from goggles_bridge.engine import BridgeEngine, BridgeSettings, check_encoder
    stop = threading.Event()
    log_path = args.log or ROOT / 'work' / 'logs' / f'{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.jsonl'

    def report(row):
        event = row['event']
        if event == 'waiting':
            print(f"Waiting / reconnecting: {row['message']}", flush=True)
        elif event == 'streaming':
            print(f'Streaming 1920x1080 at target {args.fps} fps, {args.bitrate_mbps} Mbps. Ctrl+C stops.', flush=True)
        elif event == 'stats':
            print(f"Sent {row['fps']:.1f} fps | queue p95 {row['queue_ms_p95']:.1f} ms | send p95 {row['send_ms_p95']:.1f} ms", flush=True)
        elif event in ('connected', 'ready', 'stopped'):
            print(event.capitalize(), flush=True)

    try:
        settings = BridgeSettings(args.dll, args.ffmpeg, fps=args.fps, bitrate_mbps=args.bitrate_mbps,
            capture=args.capture, capture_fps=args.capture_fps, display_index=args.display,
            show_cursor=not args.hide_cursor, preset=args.preset, keyframe_seconds=args.keyframe_seconds,
            low_latency=args.low_latency, usb_write_size=args.usb_write_size, h264_profile=args.h264_profile)
        print('Checking FFmpeg...', flush=True)
        problem = check_encoder(settings)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        engine = BridgeEngine(settings, log_path, on_event=report, stop_event=stop,
            stop_file=args.stop_file, duration=args.seconds, reconnect=not args.no_reconnect)
        previous_handler = signal.signal(signal.SIGINT, lambda *_: stop.set())
        print(f'Log: {log_path}\nPower the goggles and open More > DJI Virtual Flight.', flush=True)
        try:
            engine.run()
        finally:
            signal.signal(signal.SIGINT, previous_handler)
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Bridge stopped: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
