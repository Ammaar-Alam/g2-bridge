"""Lease an owned virtual display for exactly the duration of a stream."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import threading

from . import displays, virtual_driver
from .display_config import active_refresh


_virtual_lease = threading.Lock()
LEASE_MUTEX = r'Local\GogglesBridge.VirtualDisplay.Lease'


def _lease_api():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


@contextmanager
def _process_lease():
    """One virtual-display owner across app instances in this Windows session."""
    kernel = _lease_api()
    handle = kernel.CreateMutexW(None, False, LEASE_MUTEX)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    owned = False
    try:
        result = kernel.WaitForSingleObject(handle, 0)
        if result == 258:  # WAIT_TIMEOUT: another stream owns the display.
            raise displays.DisplayError('Another app is using the virtual display.')
        if result not in (0, 0x80):  # WAIT_OBJECT_0 or WAIT_ABANDONED.
            raise ctypes.WinError(ctypes.get_last_error())
        # An abandoned mutex transfers ownership after a crashed owner.
        # Reconfigure and verify the existing owned display before using it.
        owned = True
        yield
    finally:
        try:
            if owned:
                if not kernel.ReleaseMutex(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)


def _discard_event(_event, **_fields):
    pass


@contextmanager
def lease(source, width=1920, height=1080, fps=60, emit=None, *, display_device=None):
    """Yield a selected display and release an owned extension on every exit.

    enable_extended owns rollback until it returns successfully. After that,
    even event callbacks and source validation are inside this cleanup scope.
    Use from the stream thread so display setup never blocks the UI thread.
    """
    emit = emit or _discard_event
    target = None
    failure = None
    acquired = False
    process_lease = None
    virtual = source == 'virtual'
    try:
        if virtual:
            if not _virtual_lease.acquire(blocking=False):
                raise displays.DisplayError('A stream already owns the virtual display.')
            acquired = True
            candidate_lease = _process_lease()
            candidate_lease.__enter__()
            process_lease = candidate_lease
            state = virtual_driver.status()
            if not state['owned']:
                raise displays.DisplayError('Install the virtual display driver from this app before streaming.')
            if not state.get('config_current'):
                raise displays.DisplayError('Update the virtual display configuration to enable the supported modes.')
            emit('preparing_display')
            target = displays.enable_extended(width, height, fps)
            emit('display_status', **virtual_driver.status())
        selected = dict(displays.select_source(source, width, height, fps, device=display_device))
        try:
            selected['refresh_rate'] = active_refresh(selected['device'])
        except (OSError, RuntimeError):
            selected['refresh_rate'] = None
        yield selected
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            if target is not None:
                # Observational callbacks must never prevent real cleanup.
                try:
                    emit('releasing_display')
                except Exception:
                    pass
                try:
                    displays.disable_extended(expected=target)
                except Exception as exc:
                    if failure is None:
                        raise
                    if hasattr(failure, 'add_note'):
                        failure.add_note(f'Virtual display cleanup failed: {exc}')
                    try:
                        emit('display_cleanup_error', message=str(exc))
                    except Exception:
                        pass
                else:
                    try:
                        emit('display_status', **virtual_driver.status())
                    except Exception:
                        pass
        finally:
            try:
                if process_lease is not None:
                    process_lease.__exit__(None, None, None)
            finally:
                if acquired:
                    _virtual_lease.release()


@contextmanager
def capture_target(settings, emit=None):
    """Compatibility entry for settings with source/dimensions/fps fields."""
    with lease(settings.source, *settings.dimensions, settings.fps, emit,
               display_device=getattr(settings, 'display_device', None)) as target:
        yield target
