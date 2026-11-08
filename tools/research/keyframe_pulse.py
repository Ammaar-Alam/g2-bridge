"""Measure per-frame size and SSIM around NVENC keyframes at several rate-control buffer sizes.

Encodes three deterministic 1920x1080 sources with the bridge's NVENC settings
and compares every decoded frame with its source. Needs FFmpeg with h264_nvenc.
"""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess

FPS, FRAMES, BITRATE = 100, 650, 20_000_000
FONT = 'C\\:/Windows/Fonts/consola.ttf'
LINE = 'The quick brown fox jumps over the lazy dog 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnop'
SOURCES = {
    # small static text, like a desktop or menu
    'text': f'color=c=white:s=1920x1080:r={FPS},' + ','.join(
        f"drawtext=fontfile='{FONT}':fontsize=18:fontcolor=black:x=20:y={20+i*26}:text='{i:02d} {LINE}'"
        for i in range(40)),
    # fine static detail
    'fractal': f'mandelbrot=s=1920x1080:r={FPS}:end_pts=0.0001:maxiter=2000,loop=loop=-1:size=1',
    # the motion source used for the encoder quality table
    'motion': f'testsrc2=size=1920x1080:rate={FPS},drawbox=x=600:y=300:w=700:h=400:color=gray:t=fill',
}
ENCODER = ['-an', '-c:v', 'h264_nvenc', '-preset', 'p4', '-tune', 'ull', '-rc', 'cbr', '-b:v', str(BITRATE),
           '-maxrate', str(BITRATE), '-zerolatency', '1', '-delay', '0', '-bf', '0', '-g', str(FPS*3),
           '-profile:v', 'high', '-level:v', '5.1', '-aud', '1', '-forced-idr', '1',
           '-bsf:v', 'filter_units=remove_types=12']
VBV_FRAMES = (2, 4, 8, 16)
KEYFRAME = 300


def measure(ffmpeg, ffprobe, folder, source, vbv_frames):
    stream = folder / f'{source}-vbv{vbv_frames}.h264'
    subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i', SOURCES[source],
                    '-frames:v', str(FRAMES), '-pix_fmt', 'yuv420p', *ENCODER,
                    '-bufsize', str(BITRATE*vbv_frames//FPS), '-f', 'h264', str(stream)], check=True)
    packets = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=size,flags',
                              '-of', 'csv=p=0', str(stream)], capture_output=True, text=True, check=True).stdout.split()
    stats = stream.with_suffix('.ssim.txt')
    subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-i', stream.name, '-f', 'lavfi', '-i', SOURCES[source],
                    '-lavfi', f"[1:v]format=yuv420p,trim=end_frame={FRAMES}[ref];[0:v][ref]ssim=stats_file='{stats.name}'",
                    '-f', 'null', '-'], check=True, cwd=folder)
    ssim = [float(re.search(r'All:([0-9.]+)', line).group(1)) for line in stats.read_text().splitlines()]
    db = [-10*math.log10(max(1-value, 1e-9)) for value in ssim]
    before = sum(db[KEYFRAME-20:KEYFRAME]) / 20
    recovery = next((i for i, value in enumerate(db[KEYFRAME:]) if value >= before-0.5), None)
    return {'source': source, 'vbv_frames': vbv_frames,
            'keyframes': [i for i, row in enumerate(packets) if 'K' in row.split(',')[1]],
            'keyframe_bytes': int(packets[KEYFRAME].split(',')[0]),
            'ssim_db_before_keyframe': round(before, 2), 'ssim_db_at_keyframe': round(db[KEYFRAME], 2),
            'recovery_frames': recovery, 'frame_bytes': [int(row.split(',')[0]) for row in packets],
            'ssim': ssim}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('work/research/keyframe-pulse'),
                        help='New folder for streams and results')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new path')
    args.output.mkdir(parents=True)
    results = []
    for source in SOURCES:
        for vbv_frames in VBV_FRAMES:
            row = measure(args.ffmpeg, args.ffprobe, args.output, source, vbv_frames)
            results.append(row)
            print(f"{source:8} vbv {vbv_frames:2}: keyframe {row['keyframe_bytes']:7} B, SSIM "
                  f"{row['ssim_db_before_keyframe']:5.1f} -> {row['ssim_db_at_keyframe']:5.1f} dB, "
                  f"recovered in {row['recovery_frames']} frames", flush=True)
    with (args.output / 'results.json').open('x', encoding='utf-8') as stream:
        json.dump(results, stream)
        stream.write('\n')


if __name__ == '__main__':
    main()
