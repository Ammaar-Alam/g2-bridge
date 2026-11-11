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
    def run_main(self, options=(), *, checks=(None,), env='', installed='ffmpeg.exe', bundled=True):
        def is_file(path):
            return bundled or path != stream_desktop.WINDOWS_ENCODER
        with patch.object(stream_desktop, 'MAC', False), patch.object(stream_desktop, 'WINDOWS', True), \
                patch.object(Path, 'is_file', is_file), \
                patch.dict(stream_desktop.os.environ, {'GOGGLES_FFMPEG': env}), \
                patch.object(stream_desktop, 'find_program', return_value=installed), \
                patch.object(stream_desktop.sys, 'argv', ['stream_desktop', '--dll', 'driver.dll', *options]), \
                patch.object(stream_desktop, 'check_encoder', side_effect=checks) as check, \
                patch.object(stream_desktop, 'BridgeEngine') as engine, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = stream_desktop.main()
        return code, check, engine

    def test_bundled_encoder_is_checked_before_streaming(self):
        for fps in (60, 75, 90, 100):
            with self.subTest(fps=fps):
                code, check, engine = self.run_main(['--fps', str(fps)], installed=None)
                self.assertEqual(code, 0)
                settings = engine.call_args.args[0]
                self.assertEqual(settings.ffmpeg, stream_desktop.WINDOWS_ENCODER)
                self.assertTrue(settings.startup_fullres)
                check.assert_called_once_with(settings)
                engine.return_value.run.assert_called_once()

    def test_driver_rejection_checks_the_fallback_before_streaming(self):
        for installed in ('ffmpeg.exe', None):
            with self.subTest(installed=installed):
                code, check, engine = self.run_main(
                    checks=('Startup multipass reconfiguration failed', None), installed=installed)
                self.assertEqual(code, 0)
                self.assertTrue(check.call_args_list[0].args[0].startup_fullres)
                settings = engine.call_args.args[0]
                self.assertFalse(settings.startup_fullres)
                self.assertEqual(settings.ffmpeg, Path(installed) if installed else stream_desktop.WINDOWS_ENCODER)
                self.assertEqual(check.call_args_list[1].args[0], settings)

    def test_capture_errors_and_failed_fallbacks_do_not_start_usb(self):
        cases = ((('No frame was captured within 30 seconds',), 'ffmpeg.exe', 1),
                 (('Startup multipass initialization failed', 'Encoder unavailable'), 'ffmpeg.exe', 2),
                 (('Startup multipass initialization failed', 'Encoder unavailable'), None, 2))
        for checks, installed, count in cases:
            with self.subTest(checks=checks, installed=installed):
                code, check, engine = self.run_main(checks=checks, installed=installed)
                self.assertEqual(code, 1)
                self.assertEqual(check.call_count, count)
                engine.assert_not_called()

    def test_explicit_paths_and_other_modes_keep_the_requested_encoder(self):
        cases = ((['--ffmpeg', 'selected.exe'], 'environment.exe', 'selected.exe'),
                 ([], 'environment.exe', 'environment.exe'),
                 (['--preset', 'p4'], '', 'ffmpeg.exe'),
                 (['--aq'], '', 'ffmpeg.exe'),
                 (['--capture', 'ddagrab'], '', 'ffmpeg.exe'))
        for options, env, expected in cases:
            with self.subTest(options=options, env=env):
                code, check, engine = self.run_main(options, env=env)
                self.assertEqual(code, 0)
                settings = engine.call_args.args[0]
                self.assertEqual(settings.ffmpeg, Path(expected))
                self.assertFalse(settings.startup_fullres)
                check.assert_called_once_with(settings)

    def test_missing_bundle_uses_the_installed_encoder(self):
        code, check, engine = self.run_main(bundled=False)
        self.assertEqual(code, 0)
        settings = engine.call_args.args[0]
        self.assertEqual(settings.ffmpeg, Path('ffmpeg.exe'))
        self.assertFalse(settings.startup_fullres)
        check.assert_called_once_with(settings)

    def test_windows_defaults_and_explicit_overrides(self):
        for options, bitrate, preset in (([], 32, 'p1'), (['--fps', '75'], 30, 'p1'),
                (['--fps', '60'], 24, 'p1'), (['--fps', '90'], 32, 'p1'),
                (['--preset', 'p4', '--bitrate-mbps', '20'], 20, 'p4')):
            with self.subTest(options=options), patch.object(stream_desktop, 'MAC', False), \
                    patch.object(Path, 'is_file', return_value=True), \
                    patch.object(stream_desktop.sys, 'argv', ['stream_desktop', '--dll', 'driver.dll',
                                                           '--ffmpeg', 'ffmpeg.exe', *options]), \
                    patch.object(stream_desktop, 'check_encoder', return_value=None) as check, \
                    patch.object(stream_desktop, 'BridgeEngine') as engine, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(stream_desktop.main(), 0)
                settings = engine.call_args.args[0]
                self.assertEqual(settings.bitrate_mbps, bitrate)
                self.assertEqual(settings.preset, preset)
                check.assert_called_once_with(settings)
                engine.return_value.run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
