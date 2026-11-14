"""Resources for the optional Windows virtual display driver."""
from pathlib import Path
import sys


def resources():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))


def maintenance_command():
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).parent/'GogglesBridgeDisplaySetup.exe'), []
    return sys.executable, [str(resources()/'scripts'/'goggles_bridge_display_setup.py')]
