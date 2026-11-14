"""Offline native worker routing, cancellation, and command parity."""
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from goggles_bridge.engine import BridgeSettings, encoder_command
from goggles_bridge.app.windows import worker, runtime
from goggles_bridge.app.windows.stream_engine import DesktopBridgeEngine
from goggles_bridge.app.windows.video import compatible_command


class TextPipe(io.StringIO):
    def reconfigure(self, **kwargs):
        pass


class NativeWorkerTests(unittest.TestCase):
    def request(self, **options):
        settings = BridgeSettings(Path('dll'), Path('native.exe'), capture='ddagrab', **options)
        values = asdict(settings)
        values.update(dll='dll', ffmpeg='native.exe')
        return dict(settings=values, display_device='selected', log='unused.jsonl')

    def test_preflight_and_live_share_target_and_advanced_policy(self):
        for startup in (False, True):
            request = self.request(fps=100, h264_profile='baseline', keyframe_seconds=1,
                                   adaptive_quant=True, low_latency=False, usb_write_size=2048)
            request['startup_only'] = startup
            output = dict(device='selected', adapter=2, output=1, vendor_id=0x10de)
            stop = threading.Event()
            with patch.object(worker, 'select_output', return_value=output), \
                 patch.object(worker, 'check_encoder', return_value=None) as check, \
                 patch.object(worker, 'DesktopBridgeEngine') as engine:
                worker.stream(request, stop, Mock())
            checked = check.call_args.args[0]
            live = engine.call_args.args[0]
            self.assertEqual(checked, live)
            self.assertEqual(live.display_index, 1)
            self.assertEqual(live.capture_fps, 100)
            self.assertEqual(live.h264_profile, 'baseline')
            self.assertTrue(live.adaptive_quant)
            self.assertEqual(live.usb_write_size, 2048)
            preflight_options = dict(check.call_args.kwargs['run'].keywords)
            self.assertIs(preflight_options.pop('stop'), stop)
            self.assertEqual(preflight_options, engine.call_args.kwargs['process_factory'].keywords)
            self.assertEqual(preflight_options, dict(output=output, startup_only=startup))
            engine.return_value.run.assert_called_once_with()

    def test_cancelled_preflight_never_opens_usb(self):
        stop = threading.Event()
        stop.set()
        with patch.object(worker, 'select_output') as select, patch.object(worker, 'DesktopBridgeEngine') as engine:
            worker.stream(self.request(), stop, Mock())
        select.assert_not_called()
        engine.assert_not_called()

    def test_journal_and_ipc_report_effective_native_encoder_policy(self):
        class SimulatedEngine(DesktopBridgeEngine):
            def _session(self, attempt):
                self.stop_event.set()

        with tempfile.TemporaryDirectory() as folder:
            for startup in (False, True):
                request = self.request(keyframe_seconds=3)
                request.update(startup_only=startup, log=str(Path(folder)/f'{startup}.jsonl'))
                rows = []
                with patch.object(worker, 'select_output', return_value=dict(adapter=0, output=1, vendor_id=0x10de)), \
                     patch.object(worker, 'check_encoder', return_value=None), \
                     patch.object(worker, 'DesktopBridgeEngine', SimulatedEngine):
                    worker.stream(request, threading.Event(), lambda **row: rows.append(row))
                journal = [json.loads(line) for line in Path(request['log']).read_text().splitlines()]
                self.assertEqual(rows, journal)
                start = journal[0]
                self.assertEqual(start['event'], 'starting')
                self.assertFalse(start['intra_refresh'])
                self.assertTrue(start['native_backend'])
                self.assertEqual(start['periodic_idr'], not startup)
                self.assertEqual(start['keyframe_seconds'], None if startup else 3)
                command = compatible_command(encoder_command(BridgeSettings(None, Path('native.exe'), capture='ddagrab')),
                                             startup_only=startup)
                self.assertEqual(command[command.index('-intra-refresh')+1], '0')

    def test_real_error_after_cancellation_is_not_swallowed(self):
        def fail(request, stop, emit):
            stop.set()
            raise RuntimeError('encoder cleanup failed')
        output = TextPipe()
        with patch.object(worker.sys, 'stdin', TextPipe(json.dumps(self.request())+'\n')), \
             patch.object(worker.sys, 'stdout', output), patch.object(worker, 'stream', side_effect=fail):
            self.assertEqual(worker.main(), 1)
        self.assertIn('encoder cleanup failed', output.getvalue())

    def test_runtime_preserves_error_from_nonzero_worker_after_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            process = Mock(stdin=io.StringIO(), stdout=io.StringIO('{"event":"error","message":"capture failed"}\n'))
            process.wait.return_value = 1
            process.poll.return_value = 1
            stop = threading.Event()
            stop.set()
            settings = BridgeSettings(Path('dll'), Path('native.exe'), capture='ddagrab')
            with patch.object(runtime.subprocess, 'Popen', return_value=process), \
                 patch.object(runtime, 'worker_command', return_value=('worker', [])):
                with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                    runtime.WindowsRuntime().run(settings, 'selected', Path(folder)/'run.jsonl', stop, Mock())


if __name__ == '__main__':
    unittest.main()
