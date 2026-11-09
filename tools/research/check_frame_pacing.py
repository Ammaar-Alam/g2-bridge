"""Verify Windows frame pacing with decoded frame IDs, without a GPU or USB.

Requires FFmpeg with select and setpts strip_fps support.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from goggles_bridge.engine import NO_WINDOW, BridgeSettings, encoder_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--output', type=Path, required=True, help='New JSON results file')
    args = parser.parse_args()
    ffmpeg = Path(shutil.which(args.ffmpeg) or args.ffmpeg).resolve()
    if not ffmpeg.is_file():
        parser.error('FFmpeg was not found')
    if args.output.exists():
        parser.error('Use a new output file')
    frames = 600
    raw = b''.join(bytes(235 if frame & (1 << bit) else 16 for bit in range(16))*16
                   for frame in range(frames))
    results = []
    for fps in (60, 75, 90, 100):
        encoder = encoder_command(BridgeSettings(None, ffmpeg, fps=fps))
        pacing = encoder[encoder.index('-vf')+1]
        for source_fps in (fps, fps-0.1, fps+0.1, 120, 144, 240, 30):
            for gap in (0, 20, 200):
                for jitter in (0, 500, -500):
                    graph = (f"settb=1/1000000,setpts='PTS+if(gte(N,300),{gap}*1000,0)"
                             f"+if(gt(N,0),(2*mod(N,2)-1)*{jitter},0)'," + pacing)
                    command = [str(ffmpeg), '-v', 'error', '-nostdin', '-f', 'rawvideo', '-pixel_format', 'gray',
                        '-video_size', '16x16', '-framerate', str(source_fps), '-i', 'pipe:0',
                        '-vf', graph, '-r', str(fps), '-fps_mode', 'cfr', '-f', 'rawvideo', 'pipe:1']
                    result = subprocess.run(command, input=raw, capture_output=True, check=True, timeout=15,
                                            creationflags=NO_WINDOW)
                    assert len(result.stdout)%256 == 0
                    ids = [sum((value>128)<<bit for bit,value in enumerate(result.stdout[i:i+16]))
                           for i in range(0, len(result.stdout), 256)]
                    case = (fps, source_fps, gap, jitter)
                    assert all(0<=index<frames for index in ids) and ids == sorted(ids), case
                    assert len(ids) == len(set(ids)), case
                    if source_fps <= fps:
                        assert ids == list(range(frames)), case
                    else:
                        assert abs(len(ids)-frames*fps/source_fps) <= 3, case
                    if gap:
                        assert 300 in ids, case
                    times = [round(Fraction(index*1_000_000)/Fraction(str(source_fps)))
                             + (gap*1000 if index>=300 else 0)
                             + ((2*(index%2)-1)*jitter if index else 0) for index in ids]
                    # Bound every consecutive output span to the target plus one frame
                    minimum_offset = -times[0]*fps/1_000_000
                    for index, timestamp in enumerate(times):
                        offset = index-timestamp*fps/1_000_000
                        assert offset-minimum_offset <= 1+fps/1_000_000, case
                        minimum_offset = min(minimum_offset, offset)
                    results.append(dict(fps=fps, source_fps=source_fps, gap_ms=gap, jitter_us=jitter,
                        frames=len(ids), distinct=len(set(ids)), duplicates=len(ids)-len(set(ids)), command=command))
    manifest = dict(ffmpeg=str(ffmpeg), ffmpeg_sha256=hashlib.sha256(ffmpeg.read_bytes()).hexdigest(), cases=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    print(f'Passed {len(results)} frame-ID checks; results: {args.output}')


if __name__ == '__main__':
    main()
