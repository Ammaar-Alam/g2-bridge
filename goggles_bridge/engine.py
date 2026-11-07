"""Capture the Windows desktop and stream H.264 over the Goggles 2 PC USB route."""
from dataclasses import dataclass
from functools import partial
from pathlib import Path
import json
import math
import queue
import subprocess
import threading
import time

from .annexb import AccessUnitStream, strip_aud
from .avi import AviPacketStream
from .control import V1Stream
from .pc_video import PcVideoPacketizer
from .session import ControlSession, SessionLost
from .windows_usb import WindowsControlUsb, UsbTransportError, USB_WRITE_SIZES


@dataclass(frozen=True)
class BridgeSettings:
    dll: Path
    ffmpeg: Path
    fps: int = 100
    bitrate_mbps: int = 20
    capture: str = 'gfxcapture'
    capture_fps: int = 240
    display_index: int = 0
    show_cursor: bool = True
    preset: str = 'p4'
    keyframe_seconds: int = 3
    low_latency: bool = True
    usb_write_size: int = 16384
    h264_profile: str = 'high'

    def __post_init__(self):
        if type(self.low_latency) is not bool:
            raise ValueError('low_latency must be a boolean')
        if type(self.usb_write_size) is not int or self.usb_write_size not in USB_WRITE_SIZES:
            raise ValueError(f'Unsupported USB write size: {self.usb_write_size}')
        for name, choices in (('fps', (60, 100)), ('bitrate_mbps', (8, 10, 12, 16, 20, 24)),
                              ('capture', ('gfxcapture', 'ddagrab')), ('preset', ('p1', 'p4')),
                              ('keyframe_seconds', (1, 3)), ('h264_profile', ('baseline', 'high'))):
            if getattr(self, name) not in choices:
                raise ValueError(f'Unsupported {name}: {getattr(self, name)}')
        if type(self.capture_fps) is not int or not self.fps <= self.capture_fps <= 1000:
            raise ValueError('Capture ceiling must be between output fps and 1000')
        if type(self.display_index) is not int or self.display_index < 0:
            raise ValueError('Display index must be a nonnegative integer')


def encoder_command(settings):
    bitrate = settings.bitrate_mbps * 1_000_000
    command = [str(Path(settings.ffmpeg).resolve()), '-hide_banner', '-nostdin', '-loglevel', 'info']
    if settings.capture == 'gfxcapture':
        source = (f'gfxcapture=monitor_idx={settings.display_index}:max_framerate={settings.capture_fps}'
                  ':width=1920:height=1080:resize_mode=scale_aspect:scale_mode=bicubic'
                  f':capture_cursor={int(settings.show_cursor)}')
        command += ['-f', 'lavfi', '-i', source, '-r', str(settings.fps), '-fps_mode', 'cfr']
    else:
        source = (f'ddagrab=output_idx={settings.display_index}:framerate={settings.fps}'
                  f':draw_mouse={int(settings.show_cursor)}')
        command += ['-f', 'lavfi', '-i', source, '-vf',
                    'hwdownload,format=bgra,scale=1920:1080:force_original_aspect_ratio=decrease:flags=fast_bilinear,'
                    'pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=nv12']
    command += ['-an', '-c:v', 'h264_nvenc', '-preset', settings.preset, '-tune', 'ull', '-rc', 'cbr',
                '-b:v', str(bitrate), '-maxrate', str(bitrate), '-bufsize', str(bitrate*2//settings.fps),
                '-zerolatency', '1', '-delay', '0', '-bf', '0', '-g', str(settings.fps*settings.keyframe_seconds),
                '-profile:v', settings.h264_profile, '-level:v', '4.2' if settings.fps == 60 else '5.1',
                '-aud', '1', '-forced-idr', '1', '-flush_packets', '1']
    if settings.low_latency:
        command += ['-bsf:v', 'filter_units=remove_types=12', '-thread_queue_size', '1', '-f', 'avi', 'pipe:1']
    else:
        command += ['-f', 'h264', 'pipe:1']
    return command


def check_encoder(settings, run=subprocess.run):
    """Encode one captured frame and return a setup problem, or None if FFmpeg can stream."""
    command = encoder_command(settings)[:-3] + ['-frames:v', '1', '-f', 'null', '-']
    try:
        result = run(command, capture_output=True, text=True, errors='replace', timeout=30,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        return 'FFmpeg did not capture a frame within 30 seconds'
    if result.returncode == 0:
        return None
    if 'Filter not found' in result.stderr:
        return (f'This FFmpeg build has no {settings.capture} capture. '
                'Update it with "winget upgrade Gyan.FFmpeg", or try --capture ddagrab')
    if 'Encoder not found' in result.stderr:
        return 'This FFmpeg build has no NVIDIA encoder. Install it with "winget install Gyan.FFmpeg"'
    details = '\n  '.join(result.stderr.strip().splitlines()[-3:])
    return f'FFmpeg test encode failed. Check the NVIDIA driver and --display index.\n  {details}'


class BridgeEngine:
    """Manage the encoder and USB session, reconnecting after link loss."""
    def __init__(self, settings, log_path, *, on_event=None, stop_event=None,
                 stop_file=None, duration=0, reconnect=True, retry_delay=1,
                 transport_factory=None, process_factory=subprocess.Popen):
        if not math.isfinite(duration) or duration < 0:
            raise ValueError('Duration must be nonnegative and finite')
        if not math.isfinite(retry_delay) or retry_delay < 0:
            raise ValueError('Retry delay must be nonnegative and finite')
        self.settings = settings
        self.log_path = Path(log_path)
        self.on_event = on_event or (lambda event: None)
        self.stop_event = stop_event or threading.Event()
        self.stop_file = Path(stop_file) if stop_file else None
        self.duration = duration
        self.reconnect = reconnect
        self.retry_delay = retry_delay
        self.transport_factory = (partial(WindowsControlUsb, write_size=settings.usb_write_size)
                                  if transport_factory is None else transport_factory)
        self.process_factory = process_factory
        self.started = None
        self.log = None
        self.waiting = None

    def stopping(self):
        return (self.stop_event.is_set() or (self.stop_file is not None and self.stop_file.exists())
                or (self.duration > 0 and time.perf_counter()-self.started >= self.duration))

    def emit(self, event, **fields):
        row = dict(seconds=round(time.perf_counter()-self.started, 6), event=event, **fields)
        self.log.write(json.dumps(row)+'\n')
        self.log.flush()
        self.on_event(row)

    def run(self):
        self.started = time.perf_counter()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('x', encoding='utf-8') as self.log:
            self.emit('starting', fps=self.settings.fps, bitrate_mbps=self.settings.bitrate_mbps,
                      capture=self.settings.capture, capture_fps=self.settings.capture_fps,
                      resolution='1920x1080', preset=self.settings.preset,
                      keyframe_seconds=self.settings.keyframe_seconds, display_index=self.settings.display_index,
                      low_latency=self.settings.low_latency, usb_write_size=self.settings.usb_write_size,
                      h264_profile=self.settings.h264_profile)
            try:
                attempt = 0
                while not self.stopping():
                    attempt += 1
                    try:
                        self._session(attempt)
                    except (UsbTransportError, SessionLost) as exc:
                        if not self.reconnect:
                            raise
                        if self.waiting != str(exc):
                            self.emit('waiting', message=str(exc))
                        self.waiting = str(exc)
                        retry_at = time.perf_counter()+self.retry_delay
                        while not self.stopping() and time.perf_counter() < retry_at:
                            self.stop_event.wait(min(.1, max(0, retry_at-time.perf_counter())))
            except Exception as exc:
                self.emit('error', message=str(exc))
                raise
            finally:
                self.emit('stopped')

    def _session(self, attempt):
        local_stop = threading.Event()
        incoming = queue.Queue(maxsize=256)
        frames = queue.Queue(maxsize=1 if self.settings.low_latency else 3)
        errors = queue.Queue()
        session = ControlSession()
        decoder = V1Stream()
        packetizer = PcVideoPacketizer()
        process = None
        threads = []
        frame_count = byte_count = previous_frames = 0
        queue_times, send_times = [], []
        last_frame = last_progress = time.perf_counter()
        encoder_path = self.log_path.with_name(f'{self.log_path.stem}.encoder-{attempt}.log')
        with self.transport_factory(self.settings.dll) as usb, encoder_path.open('x', encoding='utf-8') as encoder_log:
            self.emit('connected', attempt=attempt)

            def read_usb():
                try:
                    while not local_stop.is_set():
                        data = usb.read(timeout_ms=50)
                        if data:
                            incoming.put(data, timeout=.2)
                except Exception as exc:
                    if not local_stop.is_set():
                        errors.put(exc)

            def read_encoder():
                splitter = AviPacketStream() if self.settings.low_latency else AccessUnitStream()
                try:
                    while not local_stop.is_set():
                        data = process.stdout.read(16384)
                        if not data:
                            raise RuntimeError(f'Capture ended. See {encoder_path}')
                        for packet in splitter.feed(data):
                            frame = strip_aud(packet) if self.settings.low_latency else packet
                            completed_at = time.perf_counter()
                            while not local_stop.is_set():
                                try:
                                    frames.put((completed_at, frame), timeout=.1)
                                    break
                                except queue.Full:
                                    pass
                except Exception as exc:
                    if not local_stop.is_set():
                        errors.put(exc)

            def send_control(packet):
                data = packet.serialize()
                usb.write(data)
                self.emit('control_send', hex=data.hex())

            try:
                thread = threading.Thread(target=read_usb, daemon=True)
                threads.append(thread)
                thread.start()
                while not self.stopping():
                    if not errors.empty():
                        raise errors.get_nowait()
                    # Accept queued replies before judging their deadlines
                    while not incoming.empty():
                        data = incoming.get_nowait()
                        self.emit('control_receive', hex=data.hex())
                        for reply in decoder.feed(data):
                            for packet in session.receive(reply, time.perf_counter()):
                                send_control(packet)
                    for packet in session.poll(time.perf_counter()):
                        send_control(packet)
                    if session.state == 'ready' and process is None:
                        self.waiting = None
                        self.emit('ready', model=session.model, identity=session.identity)
                        process = self.process_factory(encoder_command(self.settings), stdout=subprocess.PIPE,
                            stderr=encoder_log, stdin=subprocess.DEVNULL, bufsize=0,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                        last_frame = time.perf_counter()
                        thread = threading.Thread(target=read_encoder, daemon=True)
                        threads.append(thread)
                        thread.start()
                    if session.state == 'ready':
                        try:
                            completed_at, frame = frames.get(timeout=.002)
                        except queue.Empty:
                            if time.perf_counter()-last_frame > 5:
                                raise RuntimeError(f'No video from display. See {encoder_path}')
                            continue
                        last_frame = time.perf_counter()
                        queue_times.append((last_frame-completed_at)*1000)
                        wire = b''.join(packet.serialize() for packet in
                                        packetizer.packetize(frame, session.reserve_sequence))
                        usb.write(wire)
                        send_times.append((time.perf_counter()-last_frame)*1000)
                        byte_count += len(wire)
                        frame_count += 1
                        if frame_count == 1:
                            self.emit('streaming', encoder_pid=process.pid)
                    else:
                        self.stop_event.wait(.002)
                    now = time.perf_counter()
                    if now-last_progress >= 5:
                        def p95(values):
                            return round(sorted(values)[int((len(values)-1)*.95)], 2) if values else 0
                        self.emit('stats', frames=frame_count, bytes=byte_count, queued_frames=frames.qsize(),
                                  fps=round((frame_count-previous_frames)/(now-last_progress), 2),
                                  queue_ms_p95=p95(queue_times), send_ms_p95=p95(send_times))
                        previous_frames, last_progress = frame_count, now
                        queue_times.clear()
                        send_times.clear()
            finally:
                local_stop.set()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                for thread in threads:
                    thread.join(timeout=1)
                if process and process.stdout:
                    process.stdout.close()
                self.emit('session_ended', frames=frame_count, bytes=byte_count,
                          discarded_bytes=decoder.discarded)
