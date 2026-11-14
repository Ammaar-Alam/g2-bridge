"""Bind the stock WGC graph to the leased display without changing encoder policy."""
from dataclasses import replace
from functools import partial
import re
import subprocess

from ...engine import BridgeEngine, check_encoder
from .display_session import lease
from .system import Cancelled, run_cancellable


class VirtualDisplayEngine(BridgeEngine):
    """Correct app-specific dimensions before the SDK writes its startup log."""
    def __init__(self, *args, dimensions, **kwargs):
        super().__init__(*args, **kwargs)
        self.dimensions = dimensions

    def emit(self, event, **fields):
        if event == 'starting':
            fields['resolution'] = f'{self.dimensions[0]}x{self.dimensions[1]}'
        return super().emit(event, **fields)


def command_for_target(command, *, target, dimensions):
    result = list(command)
    index = result.index('-i') + 1
    graph = result[index]
    if not graph.startswith('gfxcapture=') or type(target.get('hmonitor')) is not int or target['hmonitor'] <= 0:
        raise ValueError('The virtual display requires Windows Graphics Capture and a valid monitor handle')
    width, height = dimensions
    if dimensions not in ((1280, 720), (1920, 1080)):
        raise ValueError('Unsupported virtual display resolution')
    graph = re.sub(r'monitor_idx=-?\d+', f"hmonitor={target['hmonitor']}", graph)
    graph = re.sub(r'width=-?\d+', f'width={width}', graph)
    graph = re.sub(r'height=-?\d+', f'height={height}', graph)
    result[index] = graph + ':display_border=0'
    return result


def run(settings, options, log, stop, on_event, *, engine_factory=BridgeEngine, check=check_encoder):
    """A stopped or disconnected stream releases only its leased display."""
    if stop.is_set():
        return
    dimensions = (1280, 720) if options['virtual_resolution'] == '720p' else (1920, 1080)
    settings = replace(settings, capture='gfxcapture', capture_fps=1000)
    cleanup_errors = []

    def display_event(event, **values):
        if event == 'display_cleanup_error':
            cleanup_errors.append(values.get('message') or 'The virtual display could not be released')
        on_event(dict(event=event, **values))

    try:
        with lease('virtual', *dimensions, settings.fps, display_event) as target:
            if stop.is_set():
                return
            adapt = partial(command_for_target, target=target, dimensions=dimensions)

            def preflight(command, **kwargs):
                return run_cancellable(adapt(command), stop, **kwargs)

            error = check(settings, run=preflight)
            if error:
                raise RuntimeError(error)
            if stop.is_set():
                return

            def encode(command, **kwargs):
                return subprocess.Popen(adapt(command), **kwargs)

            # Upstream reconnect loops retain the session; virtual streams instead
            # end on link loss so that the independent desktop can be released.
            factory = partial(VirtualDisplayEngine, dimensions=dimensions) if engine_factory is BridgeEngine else engine_factory
            factory(settings, log, stop_event=stop, on_event=on_event,
                    reconnect=False, process_factory=encode).run()
    except Exception as exc:
        if cleanup_errors:
            raise RuntimeError(f'{str(exc) or "Stream cancelled"}; virtual display cleanup failed: {cleanup_errors[-1]}') from exc
        if not isinstance(exc, Cancelled):
            raise
