"""Compare encoder startup sizes on repeated copies of a generated image.

Requires an NVIDIA GPU and a full FFmpeg build for generating and decoding
the reference. Does not capture the screen or open USB.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from goggles_bridge.avi import AviPacketStream
from goggles_bridge.engine import BridgeSettings, MAX_FRAME_BYTES, NO_WINDOW, encoder_command
from tools.research.check_refresh_frames import detail_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg used to generate and decode the reference')
    parser.add_argument('--encoder', type=Path,
                        default=ROOT/'vendor/ffmpeg/windows-x64/g2-encoder.exe', help='Windows encoder helper')
    parser.add_argument('--fps', type=int, choices=(60, 75, 90, 100), default=75)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    ffmpeg = Path(shutil.which(args.ffmpeg) or args.ffmpeg).resolve()
    encoder = args.encoder.resolve()
    if not ffmpeg.is_file() or not encoder.is_file():
        parser.error('Both FFmpeg and the Windows encoder helper must exist')
    folder = args.output.resolve()
    if folder.exists():
        parser.error('Use a new output directory')
    folder.mkdir(parents=True)
    source = detail_source(args.fps)
    generated = subprocess.run([str(ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', source,
        '-frames:v', '1', '-pix_fmt', 'bgra', '-f', 'rawvideo', 'pipe:1'],
        capture_output=True, check=True, timeout=90, creationflags=NO_WINDOW)
    frame = generated.stdout
    assert not generated.stderr and len(frame) == 1920*1080*4
    results = dict(fps=args.fps, frames=8, source=source,
        source_frame_md5=hashlib.md5(frame).hexdigest(),
        source_ffmpeg_sha256=hashlib.sha256(ffmpeg.read_bytes()).hexdigest(),
        encoder_sha256=hashlib.sha256(encoder.read_bytes()).hexdigest(), runs=[])
    for mode, enabled in (('standard', False), ('startup-protected', True)):
        command = encoder_command(BridgeSettings(None, encoder, fps=args.fps, startup_fullres=enabled))
        command = command[:command.index('-f')] + ['-f', 'rawvideo', '-pixel_format', 'bgra',
            '-video_size', '1920x1080', '-framerate', str(args.fps), '-i', 'pipe:0'] + command[command.index('-vf'):]
        command[-1:-1] = ['-frames:v', '8']
        encoded = subprocess.run(command, input=frame*8, capture_output=True, timeout=30, creationflags=NO_WINDOW)
        (folder/f'{mode}.log').write_bytes(encoded.stderr)
        encoded.check_returncode()
        reader = AviPacketStream()
        packets = reader.feed(encoded.stdout)
        reader.finish()
        assert len(packets) == 8
        video = folder/f'{mode}.h264'
        video.write_bytes(b''.join(packets))
        decoded = subprocess.run([str(ffmpeg), '-v', 'error', '-xerror', '-i', str(video),
            '-fps_mode', 'passthrough', '-f', 'framemd5', 'pipe:1'],
            capture_output=True, check=True, timeout=30, creationflags=NO_WINDOW)
        rows = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b'#')]
        assert not decoded.stderr and len(rows) == 8
        (folder/f'{mode}.framemd5').write_bytes(decoded.stdout)
        sizes = list(map(len, packets))
        results['runs'].append(dict(mode=mode, command=command, picture_bytes=sizes,
            maximum_bytes=max(sizes), oversize_indexes=[i for i, size in enumerate(sizes) if size > MAX_FRAME_BYTES],
            stream_sha256=hashlib.sha256(video.read_bytes()).hexdigest()))
        (folder/'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f'{mode}: maximum {max(sizes)} bytes, {len(results["runs"][-1]["oversize_indexes"])} oversized pictures', flush=True)
    if results['runs'][-1]['oversize_indexes']:
        raise RuntimeError('Startup protection exceeds the picture-size limit on this configuration')


if __name__ == '__main__':
    main()
