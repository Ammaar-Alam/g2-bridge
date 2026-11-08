from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'darwin', 'Requires macOS CoreMedia and ScreenCaptureKit')
class MacFrameRateTests(unittest.TestCase):
    def test_native_limiter_with_high_and_low_refresh_sources(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / 'frame-rate-test'
            definitions, boundary, _ = (root / 'goggles_bridge/mac_capture.swift').read_text().partition('#if !FRAME_RATE_TEST')
            self.assertTrue(boundary, 'Missing capture entrypoint boundary')
            source = Path(folder) / 'mac_capture.swift'
            source.write_text(definitions)
            subprocess.run(['xcrun', 'swiftc', '-parse-as-library', str(source),
                            str(root / 'tests/mac_frame_rate.swift'), '-o', str(executable)],
                           check=True, timeout=120)
            subprocess.run([str(executable)], check=True, timeout=10)
