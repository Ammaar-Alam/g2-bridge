"""Separate elevation entry point; accepts only fixed driver maintenance verbs."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goggles_bridge.app.virtual_display.virtual_driver import maintenance_main

if __name__ == '__main__':
    raise SystemExit(maintenance_main(sys.argv[1:]))
