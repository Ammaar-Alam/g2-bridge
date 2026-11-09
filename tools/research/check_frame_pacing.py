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
from goggles_bridge.engine import BridgeSettings, encoder_command


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
        for source_fps in (fps, 240, 30):
            for gap in (0, 20, 200):
                for mode in ('previous', 'default'):
                    graph = f"settb=1/1000000,setpts='PTS+if(gte(N,300),{gap}*1000,0)'"
                    if mode == 'default':
                        graph += ',' + pacing
                    command = [str(ffmpeg), '-v', 'error', '-nostdin', '-f', 'rawvideo', '-pixel_format', 'gray',
                        '-video_size', '16x16', '-framerate', str(source_fps), '-i', 'pipe:0',
                        '-vf', graph, '-r', str(fps), '-fps_mode', 'cfr', '-f', 'rawvideo', 'pipe:1']
                    result = subprocess.run(command, input=raw, capture_output=True, check=True, timeout=15,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    assert len(result.stdout)%256 == 0
                    ids = [sum((value>128)<<bit for bit,value in enumerate(result.stdout[i:i+16]))
                           for i in range(0, len(result.stdout), 256)]
                    case = (fps, source_fps, gap, mode)
                    assert all(0<=index<frames for index in ids) and ids == sorted(ids), case
                    if mode == 'default':
                        assert len(ids) == len(set(ids)), case
                        expected, previous = [], None
                        for index in range(frames):
                            tick = round(Fraction(index*1_000_000, source_fps)) + (gap*1000 if index>=300 else 0)
                            bucket = (2*tick+1)*fps//2_000_000
                            if bucket != previous:
                                expected.append(index)
                                previous = bucket
                        assert ids == expected, case
                        if source_fps <= fps:
                            assert ids == list(range(frames)), case
                    elif source_fps == fps:
                        assert len(ids)-len(set(ids)) == round(Fraction(gap*fps, 1000)), case
                    results.append(dict(fps=fps, source_fps=source_fps, gap_ms=gap, mode=mode,
                        frames=len(ids), distinct=len(set(ids)), duplicates=len(ids)-len(set(ids)), command=command))
    manifest = dict(ffmpeg=str(ffmpeg), ffmpeg_sha256=hashlib.sha256(ffmpeg.read_bytes()).hexdigest(), cases=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    print(f'Passed {len(results)} frame-ID checks; results: {args.output}')


if __name__ == '__main__':
    main()
