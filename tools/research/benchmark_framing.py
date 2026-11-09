"""Compare host frame-release times using the same paced encoder output."""
from pathlib import Path
import argparse
import hashlib
import threading
import json
import statistics
import struct
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from goggles_bridge.avi import AviPacketStream
from goggles_bridge.annexb import AccessUnitStream


class RawPayloadTap:
    """Expose codec bytes as they arrive, before an AVI packet is complete."""
    def __init__(self):
        self.buffer = bytearray()
        self.started = False
        self.remaining = 0
        self.padding = 0
        self.tag = None

    def feed(self, data):
        self.buffer.extend(data)
        result = []
        if not self.started:
            marker = self.buffer.find(b'LIST\xff\xff\xff\xffmovi')
            if marker < 0:
                assert len(self.buffer) < 65536
                return result
            del self.buffer[:marker+12]
            self.started = True
        while True:
            if self.remaining:
                count = min(self.remaining, len(self.buffer))
                if not count:
                    break
                if self.tag == b'00dc':
                    result.append(bytes(self.buffer[:count]))
                del self.buffer[:count]
                self.remaining -= count
                continue
            if self.padding:
                if not self.buffer:
                    break
                del self.buffer[:1]
                self.padding = 0
            if len(self.buffer) < 8:
                break
            self.tag, self.remaining = struct.unpack_from('<4sI', self.buffer)
            assert self.tag in (b'00dc', b'JUNK', b'idx1')
            assert self.remaining < 2*1024*1024
            self.padding = self.remaining&1
            del self.buffer[:8]
        return result


def run(ffmpeg, base, label, source):
    command = [str(ffmpeg), '-hide_banner', '-nostdin', '-loglevel', 'warning', '-re',
        '-f', 'lavfi', '-i', source, '-frames:v', '300', '-an', '-c:v', 'h264_nvenc',
        '-preset', 'p4', '-tune', 'ull', '-rc', 'cbr', '-b:v', '20000000', '-maxrate', '20000000',
        '-bufsize', '400000', '-zerolatency', '1', '-delay', '0', '-bf', '0', '-g', '300',
        '-profile:v', 'baseline', '-level:v', '5.1', '-aud', '1', '-forced-idr', '1',
        '-flush_packets', '1', '-thread_queue_size', '1', '-f', 'avi', 'pipe:1']
    avi, raw, tap = AviPacketStream(), AccessUnitStream(), RawPayloadTap()
    immediate, delayed, frame_hashes, raw_hashes = [], [], [], []
    started = time.perf_counter()
    with (base/f'{label}.log').open('w') as log, (base/f'{label}.avi').open('wb') as capture:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log,
            stdin=subprocess.DEVNULL, bufsize=0, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        watchdog = threading.Timer(20, process.kill)
        watchdog.start()
        try:
            while True:
                data = process.stdout.read(16384)
                read_at = time.perf_counter()-started
                if not data:
                    break
                if read_at > 15:
                    raise RuntimeError('Benchmark exceeded duration bound')
                capture.write(data)
                for packet in avi.feed(data):
                    immediate.append(read_at)
                    frame_hashes.append(hashlib.sha256(packet).hexdigest())
                for piece in tap.feed(data):
                    for frame in raw.feed(piece):
                        delayed.append(read_at)
                        raw_hashes.append(hashlib.sha256(frame).hexdigest())
            avi.finish()
            if process.wait(timeout=3):
                raise RuntimeError(f'Encoder failed; see {label}.log')
        finally:
            watchdog.cancel()
            if process.poll() is None:
                process.kill();process.wait(timeout=3)
            process.stdout.close()
    assert len(immediate)==300 and len(delayed)==299
    assert frame_hashes[:-1]==raw_hashes
    holds = [1000*(b-a) for a,b in zip(immediate, delayed)]
    assert min(holds) >= 0
    result = dict(source=source, frames=300, compared_frames=len(holds),
        held_ms_median=statistics.median(holds), held_ms_p95=sorted(holds)[int(.95*(len(holds)-1))],
        held_ms_min=min(holds), held_ms_max=max(holds), immediate_times=immediate, delayed_times=delayed)
    (base/f'{label}.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if not k.endswith('_times')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    ffmpeg = args.ffmpeg.resolve(strict=True)
    base = args.out_dir.resolve()
    if base.exists(): parser.error('Output directory already exists')
    base.mkdir(parents=True)
    run(ffmpeg, base, 'paired-gray', 'color=c=gray:size=1920x1080:rate=100')
    run(ffmpeg, base, 'paired-motion', 'testsrc2=size=1920x1080:rate=100')
