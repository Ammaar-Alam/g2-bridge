"""Native DDA preflight and USB sending, isolated from the WebView process."""
from dataclasses import replace
from functools import partial
import json
from pathlib import Path
import sys
import threading

from ...engine import BridgeSettings, check_encoder
from .dxgi import select_output
from .stream_engine import DesktopBridgeEngine
from .system import Cancelled
from .video import start_encoder, check_capture


def stream(request, stop, emit):
    values = dict(request['settings'])
    for key in ('dll', 'ffmpeg'):
        values[key] = Path(values[key]) if values[key] else None
    settings = BridgeSettings(**values)
    if settings.capture != 'ddagrab':
        raise ValueError('Native capture requires Desktop Duplication and NVIDIA NVENC')
    if stop.is_set():
        return
    output = select_output(request['display_device'])
    settings = replace(settings, display_index=output['output'], capture_fps=settings.fps)
    capture = dict(output=output, startup_only=request.get('startup_only', False))
    error = check_encoder(settings, run=partial(check_capture, stop=stop, **capture))
    if error:
        raise RuntimeError(error)
    if stop.is_set():
        raise Cancelled()
    def on_event(row):
        if row['event'] == 'starting':
            # The engine records the same row after the callback, so both IPC
            # and the journal describe the effective adapted encoder command.
            row.update(intra_refresh=False, native_backend=True,
                configured_keyframe_seconds=settings.keyframe_seconds,
                keyframe_seconds=None if capture['startup_only'] else settings.keyframe_seconds,
                periodic_idr=not capture['startup_only'],
                bootstrap_idr_seconds=[0, 1, 2] if capture['startup_only'] else None,
                capture_adapter=output['adapter'], capture_output=output['output'],
                capture_gpu=output.get('gpu_name'), capture_adapter_luid=output.get('adapter_luid'),
                gpu_resident=output.get('vendor_id') == 0x10de,
                raw_frame_queue='latest single slot', nvenc_async=True)
        emit(**row)

    engine = DesktopBridgeEngine(settings, Path(request['log']), stop_event=stop,
        on_event=on_event, process_factory=partial(start_encoder, **capture))
    engine.run()


def main():
    from .events import EventWriter
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    sys.stdin.reconfigure(encoding='utf-8')
    writer = EventWriter(sys.stdout)
    stop = threading.Event()

    def commands():
        for line in sys.stdin:
            try:
                if json.loads(line).get('command') == 'stop':
                    stop.set()
            except (ValueError, AttributeError):
                pass
        stop.set()

    try:
        request = json.loads(sys.stdin.readline())
        threading.Thread(target=commands, daemon=True).start()
        stream(request, stop, writer.emit)
        return 0
    except Cancelled:
        return 0
    except Exception as exc:
        writer.emit('error', message=str(exc))
        return 1
    finally:
        writer.close()
