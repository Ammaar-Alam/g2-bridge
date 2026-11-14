"""Windows inventory and process helpers. No SDK implementation is patched."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class Cancelled(Exception):
    pass


def run_cancellable(command, stop, timeout=30, **kwargs):
    # Adapter for SDK check_encoder's subprocess.run injection point.
    kwargs.pop('capture_output', None)
    kwargs.pop('text', None)
    kwargs.pop('errors', None)
    kwargs.setdefault('creationflags', NO_WINDOW)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    deadline = time.monotonic()+timeout
    try:
        while True:
            if stop.is_set():
                raise Cancelled()
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                out, err = process.communicate(timeout=.1)
                return subprocess.CompletedProcess(command, process.returncode,
                    out.decode('utf-8', errors='replace'), err.decode('utf-8', errors='replace'))
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


def powershell_json(script, timeout=15):
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    env = os.environ.copy()
    # A terminal using PowerShell 7 may pass its incompatible modules to the
    # system Windows PowerShell 5.1 child. Only load that child's own modules.
    env['PSModulePath'] = str(executable.parent / 'Modules')
    result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-Command',
        '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); '+script],
        capture_output=True, timeout=timeout, creationflags=NO_WINDOW, env=env)
    if result.returncode:
        raise RuntimeError('Windows system information query failed')
    return json.loads(result.stdout.decode('utf-8-sig').strip() or 'null')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()
