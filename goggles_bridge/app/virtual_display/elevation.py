"""Launch a fixed maintenance operation with normal Windows UAC."""
import ctypes
from ctypes import wintypes


class InstallerProcess:
    def _launch(self, program, arguments):

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('fMask', wintypes.ULONG), ('hwnd', wintypes.HWND),
                        ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR),
                        ('lpParameters', wintypes.LPCWSTR), ('lpDirectory', wintypes.LPCWSTR),
                        ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE),
                        ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR),
                        ('hkeyClass', wintypes.HKEY), ('dwHotKey', wintypes.DWORD),
                        ('hIcon', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]

        info = SHELLEXECUTEINFO()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = 0x40 | 0x400  # NOCLOSEPROCESS, FLAG_NO_UI
        info.lpVerb = 'runas'
        info.lpFile = program
        info.lpParameters = arguments
        info.nShow = 0
        execute = ctypes.WinDLL('shell32', use_last_error=True).ShellExecuteExW
        execute.argtypes = [ctypes.POINTER(SHELLEXECUTEINFO)]
        execute.restype = wintypes.BOOL
        if not execute(ctypes.byref(info)):
            code = ctypes.get_last_error()
            raise OSError(code, 'Windows authorization was cancelled.' if code == 1223 else 'Could not start Windows driver setup.')
        self.handle = info.hProcess

    def poll(self):
        if not self.handle:
            return 0
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        get_exit = kernel.GetExitCodeProcess
        get_exit.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit.restype = wintypes.BOOL
        code = wintypes.DWORD()
        if not get_exit(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value == 259:
            return None
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close(self.handle)
        self.handle = None
        return code.value
