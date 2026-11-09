"""Stream a stereo test pattern to check whether the goggles show a different view to each eye.

The left view has a red border and the right view a blue border. Close one eye
at a time and note which colors each eye sees. The control handshake and video
packets are the same as the desktop bridge; only the encoded picture changes.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from goggles_bridge.control import V1Stream
from goggles_bridge.engine import BridgeEngine, BridgeSettings, encoder_command, find_program

# name: (size of each view, how the views are combined)
LAYOUTS = {
    'sbs': ('960x1080', 'hstack'),    # half side-by-side in the usual 1920x1080 frame
    'fsbs': ('1920x1080', 'hstack'),  # full side-by-side, 3840x1080
    'ftb': ('1920x1080', 'vstack'),   # full top-bottom, 1920x2160
}
# Packets the goggles sent in every recorded desktop session (command set, id)
BASELINE = {(0x00, 0x00), (0x00, 0x81), (0x00, 0xff), (0x09, 0x43), (0x0b, 0x1a)}


def pattern(layout, fps):
    size, stack = LAYOUTS[layout]
    # gray content keeps the borders the only color in each view
    return (f'testsrc2=size={size}:rate={fps},hue=s=0,split[a][b];[a]drawbox=color=red:t=96[l];'
            f'[b]drawbox=color=blue:t=96[r];[l][r]{stack},realtime[out0]')


def probe_command(settings, layout, stereo_sei=False):
    """Encode a synthetic stereo source, optionally with explicit layout metadata."""
    if stereo_sei:
        packing = 4 if layout == 'ftb' else 3
        return [str(settings.ffmpeg), '-hide_banner', '-nostdin', '-loglevel', 'info',
                '-f', 'lavfi', '-i', pattern(layout, settings.fps), '-an',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-crf', '18',
                '-profile:v', 'high', '-level:v', '4.2' if layout == 'sbs' else '5.1',
                '-bf', '0', '-g', str(settings.fps),
                '-x264-params', f'frame-packing={packing}:repeat-headers=1:aud=1',
                '-bsf:v', 'filter_units=remove_types=12', '-flush_packets', '1', '-f', 'avi', 'pipe:1']
    command = encoder_command(settings)
    command[command.index('-i')+1] = pattern(layout, settings.fps)
    # 3840x1080 and 1920x2160 at 60 fps need level 5.1
    command[command.index('-level:v')+1] = '5.1'
    return command


def inbound_summary(log_path):
    """Count goggles packets by (command set, id, sender type, sender id)."""
    decoder, counts = V1Stream(), Counter()
    with open(log_path, encoding='utf-8') as log:
        for line in log:
            row = json.loads(line)
            if row['event'] == 'control_receive':
                for packet in decoder.feed(bytes.fromhex(row['hex'])):
                    counts[packet.command_set, packet.command_id, packet.sender_type, packet.sender_id] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('layout', choices=LAYOUTS)
    parser.add_argument('--stereo-sei', action='store_true',
                        help='Encode left/right layout metadata with libx264; diagnostic only')
    parser.add_argument('--seconds', type=float, default=60, help='Duration, including waiting for the goggles')
    parser.add_argument('--dll', type=Path, help='Windows only (default: DJI_USB_DLL or the installed driver copy)')
    parser.add_argument('--ffmpeg', type=Path, default=os.environ.get('GOGGLES_FFMPEG') or find_program('ffmpeg'))
    parser.add_argument('--python-deps', type=Path, help='Optional directory containing PyUSB 1.3.1')
    parser.add_argument('--stop-file', type=Path, help='Stop if this file is created')
    parser.add_argument('--log', type=Path, help='New JSON Lines log (default: work/logs/stereo-LAYOUT-TIME.jsonl)')
    args = parser.parse_args()
    if not 0 < args.seconds <= 600:
        parser.error('--seconds must be between 0 and 600')
    if args.ffmpeg is None or not args.ffmpeg.is_file():
        parser.error('--ffmpeg file not found')
    if args.python_deps:
        sys.path.insert(0, str(args.python_deps.resolve()))
    settings = BridgeSettings(args.dll, args.ffmpeg, fps=60)
    command = probe_command(settings, args.layout, args.stereo_sei)
    log_path = args.log or Path(__file__).resolve().parents[2] / 'work' / 'logs' / (
        f'stereo-{args.layout}-{datetime.now():%Y%m%d-%H%M%S}.jsonl')
    print(f'Layout {args.layout}. Log: {log_path}\nOpen More > DJI Virtual Flight. Ctrl+C stops.', flush=True)
    def report(row):
        if not row['event'].startswith('control_'):
            print(row['event'], row.get('message', ''), flush=True)

    print('Encoder: libx264 with stereo metadata' if args.stereo_sei else 'Encoder: NVENC', flush=True)
    engine = BridgeEngine(settings, log_path, duration=args.seconds, on_event=report, stop_file=args.stop_file,
                          process_factory=lambda _, **options: subprocess.Popen(command, **options))
    try:
        engine.run()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
    for (command_set, command_id, sender_type, sender_id), count in inbound_summary(log_path).most_common():
        new = '' if (command_set, command_id) in BASELINE else '  NEW'
        print(f'{command_set:02x}/{command_id:02x} from {sender_type}/{sender_id}: {count}{new}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
