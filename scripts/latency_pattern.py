"""Show a repeating patch for filming monitor-to-goggles delay."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goggles_bridge.engine import find_program

PATTERN = (
    'testsrc2=size=1280x720:rate=120,'
    'drawbox=x=400:y=200:w=480:h=320:color=black:t=fill,'
    "drawbox=x=400:y=200:w=480:h=320:color=white:t=fill:enable='gte(mod(t,1.3),0.65)'"
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffplay', type=Path, help='Path to ffplay.exe (default: PATH or the winget Links folder)')
    parser.add_argument('--seconds', type=int, default=900, help='Window duration in seconds (default: 900)')
    args = parser.parse_args(argv)
    if args.seconds < 1:
        parser.error('--seconds must be positive')
    player = args.ffplay or find_program('ffplay')
    if player is None or not Path(player).is_file():
        parser.error('FFplay not found. Install an FFmpeg build that includes ffplay, or pass --ffplay with its path')
    command = [str(player), '-hide_banner', '-loglevel', 'warning', '-window_title',
               'Goggles Bridge latency test - film the center square', '-x', '1280', '-y', '720',
               '-an', '-f', 'lavfi', '-i', PATTERN, '-t', str(args.seconds)]
    print('Start the desktop bridge separately and place this window on the captured display.\n'
          'Film the center square on the monitor and through one goggle lens together.\n'
          'Use 240 fps Slo-mo and keep the original recording. Escape closes the pattern.', flush=True)
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as error:
        parser.exit(1, f'Cannot start FFplay: {error}\n')
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
