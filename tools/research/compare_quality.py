"""Compare old and new Windows encoding on synthetic 1080p video, without USB or screen capture.

Requires FFmpeg with NVENC, ffprobe beside it, and Windows Consolas for the text source.
Outputs encoded clips, commands, per-frame metrics, and whole-sequence PSNR.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from goggles_bridge.annexb import strip_aud
from goggles_bridge.avi import AviPacketStream
from goggles_bridge.engine import BridgeSettings, encoder_command


def run(command, log, folder):
    with log.open('x', encoding='utf-8') as stream:
        subprocess.run(command, cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=stream, check=True, timeout=180,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def comparison_command(ffmpeg, preset, fps=100):
    settings = BridgeSettings(Path('unused.dll'), ffmpeg, fps=fps,
                              preset='p4' if preset == 'previous' else 'p1',
                              bitrate_mbps=20 if preset == 'previous' else 32)
    command = encoder_command(settings)
    if preset == 'previous':
        for flag in ('-multipass', '-intra-refresh', '-single-slice-intra-refresh'):
            at = command.index(flag)
            del command[at:at+2]
    return command


def measure(ffmpeg, folder, scene, source, preset, frames, fps=100):
    label = f'{scene}-{preset}'
    video = folder/f'{label}.avi'
    command = comparison_command(ffmpeg, preset, fps)
    command[command.index('-i')+1] = source
    command[-1:] = ['-frames:v', str(frames), str(video)]
    run(command, folder/f'{label}.encode.log', folder)
    reader = AviPacketStream()
    packets = reader.feed(video.read_bytes())
    reader.finish()
    assert len(packets) == frames, (label, len(packets), frames)
    sizes = [len(strip_aud(packet)) for packet in packets]
    ffprobe = ffmpeg.with_name('ffprobe'+ffmpeg.suffix)
    probe = subprocess.run([str(ffprobe), '-v', 'error', '-count_frames', '-show_entries',
        'stream=width,height,has_b_frames,nb_read_frames', '-of', 'json', str(video)],
        capture_output=True, check=True, timeout=180)
    metadata = json.loads(probe.stdout)['streams'][0]
    assert metadata == dict(width=1920, height=1080, has_b_frames=0, nb_read_frames=str(frames)), metadata
    graph = (f'[0:v]trim=end_frame={frames},setpts=N/({fps}*TB),split[ra][rb];'
             f'[1:v]setpts=N/({fps}*TB),split[ea][eb];'
             f'[ea][ra]ssim=stats_file={label}.ssim[a];'
             f'[eb][rb]psnr=stats_file={label}.psnr[b]')
    metrics = [str(ffmpeg), '-hide_banner', '-nostdin', '-xerror', '-f', 'lavfi', '-i', source,
        '-i', str(video), '-filter_complex', graph, '-map', '[a]', '-map', '[b]',
        '-frames:v:0', str(frames), '-frames:v:1', str(frames), '-f', 'null', '-']
    log = folder/f'{label}.metrics.log'
    run(metrics, log, folder)
    ssims = [float(re.search(r'All:([\d.]+)', line)[1])
             for line in (folder/f'{label}.ssim').read_text().splitlines()]
    psnrs = [float(re.search(r'psnr_avg:([\w.]+)', line)[1])
             for line in (folder/f'{label}.psnr').read_text().splitlines()]
    assert len(ssims) == len(psnrs) == frames
    sequence_psnr = float(re.search(r'PSNR y:.*?average:([\w.]+)', log.read_text())[1])
    error = statistics.mean(10**(-value/10) for value in psnrs)
    reconstructed = -10*math.log10(error) if error else math.inf
    # per-frame PSNR is rounded to two decimals in FFmpeg's stats file
    assert reconstructed == sequence_psnr or abs(reconstructed-sequence_psnr) <= .00501
    result = dict(scene=scene, preset=preset, frames=frames, metadata=metadata,
        psnr_sequence_db=sequence_psnr if math.isfinite(sequence_psnr) else None,
        ssim_mean=statistics.mean(ssims), ssim_min=min(ssims),
        picture_bytes_max=max(sizes), picture_bytes_total=sum(sizes),
        picture_bytes=sizes, ssim=ssims,
        frame_psnr_db=[value if math.isfinite(value) else None for value in psnrs],
        lossless_frames=[index for index, value in enumerate(psnrs) if math.isinf(value)],
        source=source, encoder_command=command, metrics_command=metrics)
    (folder/f'{label}.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(f'{scene}/{preset}: sequence PSNR {sequence_psnr:.3f} dB, '
          f'SSIM {result["ssim_mean"]:.6f}, largest picture {max(sizes)} bytes', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--frames', type=int, default=1800)
    parser.add_argument('--fps', type=int, choices=(60, 75, 90, 100), default=100)
    parser.add_argument('--sources', nargs='+', choices=('motion', 'text', 'cuts', 'detail'),
                        default=['motion', 'text', 'cuts', 'detail'])
    args = parser.parse_args()
    ffmpeg = Path(shutil.which(args.ffmpeg) or args.ffmpeg).resolve()
    if not ffmpeg.is_file() or not ffmpeg.with_name('ffprobe'+ffmpeg.suffix).is_file():
        parser.error('FFmpeg and ffprobe must exist in the same directory')
    if not 301 <= args.frames <= 6000:
        parser.error('--frames must be between 301 and 6000')
    if args.output.exists():
        parser.error('Use a new output directory')
    sources = dict(motion='testsrc2=size=1920x1080:rate=100,drawbox=x=0:y=0:w=640:h=240:color=gray:t=fill',
        cuts="testsrc2=size=1920x1080:rate=100,negate=enable='gte(mod(n,347),211)'",
        detail=f'mandelbrot=size=1920x1080:rate=100:end_pts={args.frames}:end_scale=0.1:maxiter=100,format=yuv420p')
    font = Path(os.environ.get('SystemRoot', 'C:/Windows'))/'Fonts/consola.ttf'
    if 'text' in args.sources:
        if not font.is_file():
            parser.error('The text source requires Windows Consolas')
        font_path = font.as_posix().replace(':', r'\:')
        line = 'The quick brown fox jumps over the lazy dog 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnop'
        sources['text'] = 'color=c=white:s=1920x1080:r=100,' + ','.join(
            f"drawtext=fontfile='{font_path}':fontsize=18:fontcolor=black:x=20:y={20+i*26}:text='{i:02d} {line}'"
            for i in range(40))
    sources = {name: source.replace('rate=100', f'rate={args.fps}').replace('r=100', f'r={args.fps}')
               for name, source in sources.items()}
    folder = args.output.resolve()
    folder.mkdir(parents=True)
    digest = hashlib.sha256()
    with ffmpeg.open('rb') as binary:
        for block in iter(lambda: binary.read(1024*1024), b''):
            digest.update(block)
    manifest = dict(ffmpeg=str(ffmpeg), ffmpeg_sha256=digest.hexdigest(), frames=args.frames, fps=args.fps,
                    sources=args.sources, font_sha256=hashlib.sha256(font.read_bytes()).hexdigest()
                    if 'text' in args.sources else None)
    (folder/'run.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for scene in dict.fromkeys(args.sources):
        for preset in ('previous', 'default'):
            measure(ffmpeg, folder, scene, sources[scene], preset, args.frames, args.fps)


if __name__ == '__main__':
    main()
