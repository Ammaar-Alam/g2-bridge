"""Build the ScreenCaptureKit helper that captures and encodes on macOS 12.3 and later."""
import hashlib
from pathlib import Path
import platform
import subprocess

SOURCE = Path(__file__).with_name('mac_capture.swift')
MIN_MACOS = (12, 3)


def supported(version=None):
    """Return whether this macOS version has ScreenCaptureKit."""
    parts = (version or platform.mac_ver()[0]).split('.')
    return tuple(int(part) for part in parts[:2] if part.isdigit()) >= MIN_MACOS


def helper_path():
    """Return the compiled helper path, keyed by the source hash so edits trigger a rebuild."""
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()[:12]
    return SOURCE.parents[1] / 'work' / 'bin' / f'mac-capture-{digest}'


def build():
    """Compile the helper with Apple's Swift compiler unless this source is already built."""
    path = helper_path()
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix('.partial')
    result = subprocess.run(['xcrun', 'swiftc', '-O', '-o', str(partial), str(SOURCE)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        details = '\n  '.join(result.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f'Cannot build the screen capture helper.\n  {details}')
    partial.replace(path)
    return path
