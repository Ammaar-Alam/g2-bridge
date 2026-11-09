import argparse
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import stream_desktop


class MacSetupTests(unittest.TestCase):
    def run_setup(self, answer, *, ffmpeg=None, libusb=None, capture='avfoundation'):
        args = argparse.Namespace(ffmpeg=ffmpeg, capture=capture)
        which = lambda name, path=None: {'brew': '/opt/homebrew/bin/brew', 'ffmpeg': '/opt/homebrew/bin/ffmpeg'}[name]
        with patch('usb.backend.libusb1.get_backend', return_value=libusb), \
                patch.object(stream_desktop.shutil, 'which', side_effect=which), \
                patch.object(stream_desktop.subprocess, 'run') as run, \
                patch('builtins.input', return_value=answer) as prompt, \
                contextlib.redirect_stderr(io.StringIO()):
            run.return_value.returncode = 0
            try:
                stream_desktop.install_mac_dependencies(argparse.ArgumentParser(), args)
            except SystemExit:
                pass
        return args, run, prompt

    def test_missing_tools_install_only_after_consent(self):
        args, run, _ = self.run_setup('n')
        run.assert_not_called()
        args, run, _ = self.run_setup('y')
        run.assert_called_once_with(['/opt/homebrew/bin/brew', 'install', 'ffmpeg', 'libusb'])
        self.assertEqual(args.ffmpeg, Path('/opt/homebrew/bin/ffmpeg'))

    def test_present_tools_are_left_alone(self):
        _, run, prompt = self.run_setup('y', ffmpeg=Path('/usr/bin/ffmpeg'), libusb=object())
        run.assert_not_called()
        prompt.assert_not_called()

    def test_screencapturekit_needs_developer_tools_but_not_ffmpeg(self):
        _, run, prompt = self.run_setup('y', capture='screencapturekit', libusb=object())
        run.assert_called_once_with(['xcode-select', '-p'], capture_output=True)
        prompt.assert_not_called()


class WindowsQualityTests(unittest.TestCase):
    def test_windows_defaults_and_explicit_overrides(self):
        for options, bitrate, preset in (([], 32, 'p1'), (['--fps', '75'], 30, 'p1'),
                (['--fps', '60'], 24, 'p1'), (['--fps', '90'], 32, 'p1'),
                (['--preset', 'p4', '--bitrate-mbps', '20'], 20, 'p4')):
            with self.subTest(options=options), patch.object(stream_desktop, 'MAC', False), \
                    patch.object(Path, 'is_file', return_value=True), \
                    patch.object(stream_desktop.sys, 'argv', ['stream_desktop', '--dll', 'driver.dll',
                                                           '--ffmpeg', 'ffmpeg.exe', *options]), \
                    patch('goggles_bridge.engine.check_encoder', return_value=None) as check, \
                    patch('goggles_bridge.engine.BridgeEngine') as engine, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(stream_desktop.main(), 0)
                settings = engine.call_args.args[0]
                self.assertEqual(settings.bitrate_mbps, bitrate)
                self.assertEqual(settings.preset, preset)
                check.assert_called_once_with(settings)
                engine.return_value.run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
