"""Verify Desktop Duplication color conversion and H.264 tags without capturing a screen.

Requires FFmpeg with NVENC and ffprobe beside it. Generates RGB swatches and
checks their conversion, encoded picture data, and color metadata.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from goggles_bridge.avi import AviPacketStream
from goggles_bridge.engine import BridgeSettings, NO_WINDOW, encoder_command, find_program

COLORS = ((0, 0, 0), (255, 255, 255), (128, 128, 128), (255, 0, 0),
          (0, 255, 0), (0, 0, 255), (255, 0, 255), (64, 128, 192))


def expected_yuv(rgb, full_range):
    red, green, blue = (value/255 for value in rgb)
    luma = .299*red+.587*green+.114*blue
    y = 255*luma if full_range else 16+219*luma
    chroma_range = 255 if full_range else 224
    u = 128+chroma_range*(blue-luma)/(2*(1-.114))
    v = 128+chroma_range*(red-luma)/(2*(1-.299))
    return [max(0, min(255, round(value))) for value in (y, u, v)]


def picture_data(packets):
    pictures = []
    for packet in packets:
        starts = list(re.finditer(rb'\x00\x00(?:\x00)?\x01', packet))
        slices = []
        for i, start in enumerate(starts):
            end = starts[i+1].start() if i+1 < len(starts) else len(packet)
            nal = packet[start.end():end]
            if nal and (nal[0] & 31) in (1, 5):
                slices.append(nal)
        assert slices
        pictures.append(slices)
    return pictures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    ffmpeg = Path(find_program(args.ffmpeg) or args.ffmpeg).resolve()
    probe = ffmpeg.with_name('ffprobe'+ffmpeg.suffix)
    if not ffmpeg.is_file() or not probe.is_file():
        parser.error('FFmpeg and ffprobe must exist in the same directory')
    if args.output.exists():
        parser.error('Use a new output directory')
    folder = args.output.resolve()
    folder.mkdir(parents=True)
    frames = 60
    results = []
    for width, height in ((1920, 1080), (2560, 1600), (3840, 2160)):
        row = b''.join(bytes((blue, green, red, 255))*(width//len(COLORS))
                       for red, green, blue in COLORS)
        source = folder/f'{width}x{height}.bgra'
        source.write_bytes(row*height)
        for full_range in (False, True):
            metadata = 'setparams=color_primaries=bt709:color_trc=iec61966-2-1'
            if full_range:
                metadata += ':range=full:colorspace=gbr'
            for fps in (60, 100):
                previous = None
                for mode in ('previous', 'declared'):
                    label = f'{width}x{height}-{int(full_range)}-{fps}-{mode}'
                    production = encoder_command(BridgeSettings(None, ffmpeg, capture='ddagrab', fps=fps))
                    scaling = production[production.index('-vf')+1].removeprefix('hwdownload,')
                    assert ':out_color_matrix=bt601' in scaling
                    if mode == 'previous':
                        scaling = scaling.replace(':out_color_matrix=bt601', '')
                    graph = f'loop=loop={frames-1}:size=1,setpts=N/({fps}*TB),{metadata},{scaling}'
                    input_args = [str(ffmpeg), '-hide_banner', '-nostdin', '-f', 'rawvideo',
                        '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
                        '-framerate', str(fps), '-i', str(source), '-vf', graph]
                    command = input_args+['-frames:v', '1', '-f', 'rawvideo', 'pipe:1']
                    raw = subprocess.run(command, capture_output=True, check=True, timeout=30, creationflags=NO_WINDOW)
                    assert len(raw.stdout) == 1920*1080*3//2
                    samples = []
                    fitted_width = min(1920, round(width*1080/height))
                    left = (1920-fitted_width)//2
                    for i, rgb in enumerate(COLORS):
                        x = left+(2*i+1)*fitted_width//(2*len(COLORS))
                        uv = 1920*1080+270*1920+(x//2)*2
                        sample = [raw.stdout[540*1920+x], raw.stdout[uv], raw.stdout[uv+1]]
                        assert all(abs(a-b) <= 1 for a, b in zip(sample, expected_yuv(rgb, full_range))), (label, rgb, sample)
                        samples.append(sample)
                    video = folder/f'{label}.avi'
                    encode = input_args+production[production.index('-an'):-1]+['-frames:v', str(frames), str(video)]
                    with (folder/f'{label}.log').open('x') as log:
                        subprocess.run(encode, stdout=subprocess.DEVNULL, stderr=log, check=True,
                                       timeout=45, creationflags=NO_WINDOW)
                    reader = AviPacketStream()
                    packets = reader.feed(video.read_bytes())
                    reader.finish()
                    assert len(packets) == frames and max(map(len, packets)) <= 56000
                    info = subprocess.run([str(probe), '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height,has_b_frames,nb_read_frames,color_range,color_space,color_transfer,color_primaries',
                        '-of', 'json', str(video)], capture_output=True, check=True, timeout=30, creationflags=NO_WINDOW)
                    stream = json.loads(info.stdout)['streams'][0]
                    expected = dict(width=1920, height=1080, has_b_frames=0, nb_read_frames=str(frames),
                        color_range='pc' if full_range else 'tv', color_primaries='bt709', color_transfer='iec61966-2-1')
                    assert all(stream[key] == value for key, value in expected.items()), (label, stream)
                    digest = hashlib.sha256(raw.stdout).hexdigest()
                    pictures = picture_data(packets)
                    if mode == 'previous':
                        previous = digest, pictures
                    else:
                        assert stream['color_space'] == 'bt470bg', stream
                        assert (digest, pictures) == previous, label
                    results.append(dict(case=label, frames=frames, raw_sha256=digest, samples=samples,
                        stream=stream, maximum_picture_bytes=max(map(len, packets)), command=encode))
                    print(f'{label}: {stream.get("color_space", "unspecified")}, {frames} decoded pictures', flush=True)
    manifest = dict(ffmpeg=str(ffmpeg), ffmpeg_sha256=hashlib.sha256(ffmpeg.read_bytes()).hexdigest(), cases=results)
    (folder/'results.json').write_text(json.dumps(manifest, indent=2))
    print(f'Passed {len(results)} color checks; converted pixels and encoded picture data match')


if __name__ == '__main__':
    main()
