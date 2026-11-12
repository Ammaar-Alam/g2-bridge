"""List attached displays in the order Windows Graphics Capture numbers them."""
import ctypes as C
import sys


def list_displays():
    """Return dicts of index, name, x, y, width, height, hz, and primary, in physical pixels."""
    if sys.platform != 'win32':
        # shortcut: other platforms report one unmeasured display, add real enumeration with the macOS app
        return [dict(index=0, name='Display 1', x=0, y=0, width=1920, height=1080, hz=0, primary=True)]
    from ctypes import wintypes as W

    class MonitorInfo(C.Structure):
        _fields_ = [('cbSize', W.DWORD), ('rcMonitor', W.RECT), ('rcWork', W.RECT),
                    ('dwFlags', W.DWORD), ('szDevice', W.WCHAR*32)]

    class DevMode(C.Structure):
        # DEVMODEW with the display branch of its union
        _fields_ = [('dmDeviceName', W.WCHAR*32), ('dmSpecVersion', W.WORD), ('dmDriverVersion', W.WORD),
                    ('dmSize', W.WORD), ('dmDriverExtra', W.WORD), ('dmFields', W.DWORD),
                    ('dmPositionX', W.LONG), ('dmPositionY', W.LONG), ('dmDisplayOrientation', W.DWORD),
                    ('dmDisplayFixedOutput', W.DWORD), ('dmColor', W.SHORT), ('dmDuplex', W.SHORT),
                    ('dmYResolution', W.SHORT), ('dmTTOption', W.SHORT), ('dmCollate', W.SHORT),
                    ('dmFormName', W.WCHAR*32), ('dmLogPixels', W.WORD), ('dmBitsPerPel', W.DWORD),
                    ('dmPelsWidth', W.DWORD), ('dmPelsHeight', W.DWORD), ('dmDisplayFlags', W.DWORD),
                    ('dmDisplayFrequency', W.DWORD), ('dmICMMethod', W.DWORD), ('dmICMIntent', W.DWORD),
                    ('dmMediaType', W.DWORD), ('dmDitherType', W.DWORD), ('dmReserved1', W.DWORD),
                    ('dmReserved2', W.DWORD), ('dmPanningWidth', W.DWORD), ('dmPanningHeight', W.DWORD)]

    user32 = C.WinDLL('user32')
    callback = C.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, C.POINTER(W.RECT), W.LPARAM)
    user32.EnumDisplayMonitors.argtypes = [W.HDC, C.POINTER(W.RECT), callback, W.LPARAM]
    user32.GetMonitorInfoW.argtypes = [W.HMONITOR, C.POINTER(MonitorInfo)]
    user32.EnumDisplaySettingsW.argtypes = [W.LPCWSTR, W.DWORD, C.POINTER(DevMode)]
    displays = []

    def visit(monitor, _dc, _rect, _param):
        info = MonitorInfo(cbSize=C.sizeof(MonitorInfo))
        mode = DevMode(dmSize=C.sizeof(DevMode))
        if user32.GetMonitorInfoW(monitor, C.byref(info)) and user32.EnumDisplaySettingsW(
                info.szDevice, 0xFFFFFFFF, C.byref(mode)):  # ENUM_CURRENT_SETTINGS
            displays.append(dict(index=len(displays), name=f'Display {len(displays)+1}',
                                 x=mode.dmPositionX, y=mode.dmPositionY,
                                 width=mode.dmPelsWidth, height=mode.dmPelsHeight,
                                 hz=mode.dmDisplayFrequency, primary=bool(info.dwFlags & 1)))
        else:
            # keep the capture numbering even when a display cannot be measured
            displays.append(dict(index=len(displays), name=f'Display {len(displays)+1}',
                                 x=0, y=0, width=1920, height=1080, hz=0, primary=False))
        return True

    user32.EnumDisplayMonitors(None, None, callback(visit), 0)
    return displays
