import argparse
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import stream_desktop


class MacSetupTests(unittest.TestCase):
    def run_setup(self, answer, *, ffmpeg=None, libusb=None):
        args = argparse.Namespace(ffmpeg=ffmpeg)
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


if __name__ == '__main__':
    unittest.main()
