"""Native opt-in must not change stock capture or upstream saved preferences."""
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from goggles_bridge.app import backend
from goggles_bridge.app.windows import paths


class NativeAppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stock = self.root/'stock.exe'
        self.stock.touch()

    def desktop(self, native):
        with patch.object(backend, 'WINDOWS', True), patch.object(backend, 'MAC', False), \
             patch.object(backend, 'find_ffmpeg', return_value=self.stock), \
             patch.object(paths, 'native_ffmpeg_path', return_value=native):
            return backend.Desktop(settings_path=self.root/'settings.json', identify=lambda: None)

    def test_no_native_input_keeps_upstream_default_and_dda(self):
        app = self.desktop(None)
        self.assertIsNone(app._native_runtime)
        self.assertEqual(app._options['capture'], 'gfxcapture')
        for capture in ('gfxcapture', 'ddagrab'):
            self.assertEqual(app._settings(dict(capture=capture)).ffmpeg, self.stock)

    def test_native_input_only_selects_dda_and_preserves_advanced_preferences(self):
        native = self.root/'native.exe'
        app = self.desktop(native)
        self.assertEqual(app._settings({}).ffmpeg, self.stock)
        settings = app._settings(dict(capture='ddagrab', preset='p1', h264_profile='baseline',
            adaptive_quant=True, keyframe_seconds=1, low_latency=False, usb_write_size=2048))
        self.assertEqual(settings.ffmpeg, native)
        self.assertEqual(settings.h264_profile, 'baseline')
        self.assertEqual(settings.keyframe_seconds, 1)
        self.assertTrue(settings.adaptive_quant)
        self.assertFalse(settings.low_latency)
        self.assertEqual(settings.usb_write_size, 2048)
        self.assertEqual(app._settings(dict(capture='gfxcapture')).ffmpeg, self.stock)

    def test_missing_opt_in_binary_is_reported_without_stock_fallback(self):
        app = self.desktop(self.root/'missing.exe')
        app._settings(dict(capture='ddagrab'))
        with patch.object(backend, 'goggles_attached', return_value=False):
            self.assertFalse(app._preflight()['ffmpeg']['ok'])

    def test_native_run_resolves_selected_gdi_name_and_does_not_run_stock_preflight(self):
        app = self.desktop(self.root/'native.exe')
        settings = app._settings(dict(capture='ddagrab', display_index=1))
        app._native_runtime = Mock()
        app._check = Mock(side_effect=AssertionError('stock preflight must not run'))
        with patch.object(backend, 'list_displays', return_value=[
            dict(index=0, device='primary'), dict(index=1, device='selected')]):
            app._run(settings, self.root/'capture.jsonl')
        app._native_runtime.run.assert_called_once_with(settings, 'selected', self.root/'capture.jsonl',
                                                       app._stop, app._event)

    def test_native_input_does_not_route_wgc_through_native_worker(self):
        app = self.desktop(self.root/'native.exe')
        app._native_runtime = Mock()
        app._engine_factory = Mock()
        app._check = Mock(return_value=None)
        settings = app._settings({})
        app._run(settings, self.root/'capture.jsonl')
        app._native_runtime.run.assert_not_called()
        app._check.assert_called_once_with(settings)
        app._engine_factory.return_value.run.assert_called_once_with()

    def test_no_unrequested_developer_vendor_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(paths.sys, 'frozen', False, create=True):
            self.assertIsNone(paths.native_ffmpeg_path())
        with patch.dict(os.environ, {'GOGGLES_NATIVE_FFMPEG': 'explicit.exe'}, clear=True):
            self.assertEqual(paths.native_ffmpeg_path(), Path('explicit.exe'))

    def test_stock_upgrade_disables_stale_optional_files(self):
        native = self.root/'ffmpeg-native'/'ffmpeg.exe'
        native.parent.mkdir()
        native.touch()
        (self.root/'GogglesBridgeWorker.exe').touch()
        marker = self.root/'native-backend.json'
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(paths.sys, 'frozen', True, create=True), \
             patch.object(paths.sys, 'executable', str(self.root/'Goggles Bridge.exe')):
            self.assertIsNone(paths.native_ffmpeg_path())
            marker.write_text(json.dumps(dict(schema=1, enabled=True)), encoding='utf-8')
            self.assertEqual(paths.native_ffmpeg_path(), native)
            marker.write_text(json.dumps(dict(schema=1, enabled=False)), encoding='utf-8')
            self.assertIsNone(paths.native_ffmpeg_path())
            self.assertTrue(native.is_file())

    def test_enabled_marker_does_not_silently_fallback_when_binary_is_missing(self):
        (self.root/'native-backend.json').write_text('{"schema":1,"enabled":true}', encoding='utf-8')
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(paths.sys, 'frozen', True, create=True), \
             patch.object(paths.sys, 'executable', str(self.root/'Goggles Bridge.exe')):
            self.assertEqual(paths.native_ffmpeg_path(), self.root/'ffmpeg-native/ffmpeg.exe')


if __name__ == '__main__':
    unittest.main()
