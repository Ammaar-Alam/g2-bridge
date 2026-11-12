"""Open the Goggles Bridge desktop app."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goggles_bridge.app.backend import main

if __name__ == '__main__':
    main()
