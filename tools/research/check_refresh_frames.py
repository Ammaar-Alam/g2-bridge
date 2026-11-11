"""Compare refresh picture sizes on a generated blank-to-detail transition.

Requires FFmpeg with NVENC. Does not capture the screen or open USB.
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


def detail_source(fps):
    return (
        f'color=gray:s=1536x1024:r={fps},format=gbrp,'
        "geq=r='st(0,if(eq(X,0),Y*1701+17,ld(0)));255*random(0)':"
        "g='st(0,if(eq(X,0),Y*1702+17,ld(0)));255*random(0)':"
        "b='st(0,if(eq(X,0),Y*1703+17,ld(0)));255*random(0)',"
        'crop=1255:837:0:0,scale=1920:1080:flags=bicubic:param0=1:param1=0,'
        'format=bgra,setparams=range=full:colorspace=gbr:'
        'color_primaries=bt709:color_trc=iec61966-2-1,loop=loop=-1:size=1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--fps', type=int, choices=(60, 75, 90, 100), default=100)
    args = parser.parse_args()
    ffmpeg = Path(shutil.which(args.ffmpeg) or args.ffmpeg).resolve()
    if not ffmpeg.is_file():
        parser.error('FFmpeg was not found')
    folder = args.output.resolve()
    if folder.exists():
        parser.error('Use a new output directory')
    folder.mkdir(parents=True)
    source = detail_source(args.fps) + ',tpad=start=1:start_mode=add:color=black'
    reference = subprocess.run([str(ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', source,
        '-frames:v', '3', '-f', 'framemd5', 'pipe:1'], capture_output=True,
        check=True, timeout=90, creationflags=NO_WINDOW)
    hashes = [line.rsplit(b',', 1)[1].strip().decode() for line in reference.stdout.splitlines()
              if line and not line.startswith(b'#')]
    assert len(hashes) == 3 and hashes[0] != hashes[1] == hashes[2], hashes
    results = dict(ffmpeg_sha256=hashlib.sha256(ffmpeg.read_bytes()).hexdigest(),
                   fps=args.fps, frames=900, source=source, source_frame_md5=hashes, runs=[])
    for label, single in (('single-slice', True), ('multi-slice', False)):
        command = encoder_command(BridgeSettings(None, ffmpeg, fps=args.fps))
        command[command.index('-i')+1] = source
        command[command.index('-single-slice-intra-refresh')+1] = str(int(single))
        video = folder/f'{label}.avi'
        command[-1:] = ['-frames:v', '900', str(video)]
        with (folder/f'{label}.log').open('x', encoding='utf-8') as log:
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=log,
                           check=True, timeout=90, creationflags=NO_WINDOW)
        reader = AviPacketStream()
        packets = reader.feed(video.read_bytes())
        reader.finish()
        assert len(packets) == 900, (label, len(packets))
        decoded = subprocess.run([str(ffmpeg), '-v', 'error', '-xerror', '-i', str(video),
            '-fps_mode', 'passthrough', '-f', 'framemd5', 'pipe:1'], capture_output=True,
            check=True, timeout=30, creationflags=NO_WINDOW)
        decoded_rows = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b'#')]
        assert not decoded.stderr and len(decoded_rows) == 900
        sizes = list(map(len, packets))
        result = dict(mode=label, command=command, picture_bytes=sizes,
                      maximum_bytes=max(sizes),
                      oversize_indexes=[i for i, size in enumerate(sizes) if size > MAX_FRAME_BYTES],
                      stream_sha256=hashlib.sha256(b''.join(packets)).hexdigest())
        results['runs'].append(result)
        (folder/f'{label}.framemd5').write_bytes(decoded.stdout)
        (folder/'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f'{label}: maximum {max(sizes)} bytes, {len(result["oversize_indexes"])} oversized pictures', flush=True)
    if results['runs'][1]['oversize_indexes']:
        raise RuntimeError('Multi-slice refresh exceeds the picture-size limit on this configuration')


if __name__ == '__main__':
    main()
