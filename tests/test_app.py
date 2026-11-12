import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from goggles_bridge.app import backend
from goggles_bridge.app.backend import Desktop, describe, problem_code
from goggles_bridge.session import SIMULATOR_SILENT

READY = dict(driver=dict(needed=True, ok=True), ffmpeg=dict(needed=True, ok=True), attached=True)


class FakeEngine:
    """Replay engine events, then hold the stream open until the app stops it."""
    events = ()

    def __init__(self, settings, log, *, on_event, stop_event):
        self.settings, self.on_event, self.stop_event = settings, on_event, stop_event

    def run(self):
        for event in self.events:
            self.on_event(dict(event))
        self.stop_event.wait(5)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings_path = Path(self.folder.name)/'settings.json'
        for name, value in (('data_dir', lambda: Path(self.folder.name)), ('goggles_attached', lambda: True)):
            patcher = mock.patch.object(backend, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def app(self, events=(), check=lambda settings: None, checks=READY):
        engine = type('Engine', (FakeEngine,), dict(events=events))
        app = Desktop(settings_path=self.settings_path, engine_factory=engine, check=check, identify=lambda: None)
        app._preflight = lambda: checks
        self.addCleanup(lambda: (app.stop(), app._thread and app._thread.join(5)))
        return app

    def wait_for(self, app, phase):
        for _ in range(200):
            if app.snapshot()['phase'] == phase:
                return app.snapshot()
            threading.Event().wait(.01)
        self.fail(f"phase stayed {app.snapshot()['phase']}, expected {phase}")

    def test_stream_events_become_window_state(self):
        events = (dict(event='connected', attempt=1),
                  dict(event='ready', model='DJI Goggles 2', identity='E3T ZV900 AC Dec 24 2024|12:34:04'),
                  dict(event='streaming', encoder_pid=1, gpu_realtime=True),
                  dict(event='stats', seconds=1.0, frames=100, bytes=1, queued_frames=0, fps=99.5, queue_ms_p95=.05,
                       send_ms_p95=.7, frame_bytes_max=43000, oversize_frames=0),
                  dict(event='oversize_frame', bytes=60000, limit=56000))
        app = self.app(events)
        self.assertEqual(app.snapshot()['phase'], 'idle')
        app.start()
        state = self.wait_for(app, 'streaming')
        self.assertEqual(state['device'], describe('DJI Goggles 2', 'E3T ZV900 AC Dec 24 2024|12:34:04'))
        self.assertEqual(state['stats'], dict(fps=99.5, send_ms_p95=.7, frame_bytes_max=43000))
        self.assertEqual(state['oversize'], 1)
        json.dumps(state)
        app.stop()
        self.assertIsNone(self.wait_for(app, 'idle')['stats'])

    def test_goggles_are_identified_and_untested_firmware_is_flagged(self):
        tested = describe('DJI Goggles 2', 'E3T ZV900 AC Aug 11 2026|07:21:27')
        self.assertEqual((tested['build'], tested['version'], tested['tested']), ('Aug 11 2026', '01.14.00.00', True))
        other = describe('DJI Goggles 2', 'E3T ZV900 AC Feb 26 2025|12:39:57')
        self.assertEqual((other['version'], other['tested'], other['tested_versions']),
                         (None, False, ['01.11.00.00', '01.14.00.00']))
        # no Integra build date is recorded, so its firmware is not judged
        self.assertIsNone(describe('DJI Goggles Integra', 'E3T ZV901 AC Jan 5 2025|10:00:00')['tested'])
        app = self.app()
        self.assertIsNone(app.snapshot()['device'])
        app._identify = lambda: ('DJI Goggles 2', 'E3T ZV900 AC Dec 24 2024|12:34:04')
        app._look()
        self.assertEqual(app.snapshot()['device']['version'], '01.11.00.00')
        app._identify = lambda: None
        app._look()
        self.assertIsNone(app.snapshot()['device'])

    def test_reconnected_goggles_replace_the_streamed_identity(self):
        present = Path(self.folder.name)/'present'
        present.touch()
        plugged, found = [True], [('DJI Goggles 2', 'E3T ZV900 AC Feb 26 2025|12:39:57')]
        for name, value in (('find_dll', lambda path=None: present), ('goggles_attached', lambda: plugged[0])):
            patcher = mock.patch.object(backend, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        ready = dict(event='ready', model='DJI Goggles 2', identity='E3T ZV900 AC Dec 24 2024|12:34:04')
        engine = type('Engine', (FakeEngine,), dict(events=(ready, dict(event='streaming', encoder_pid=1, gpu_realtime=True))))
        app = Desktop(settings_path=self.settings_path, engine_factory=engine, check=lambda settings: None,
                      identify=lambda: found[0])
        app._ffmpeg = present
        self.addCleanup(lambda: (app.stop(), app._thread and app._thread.join(5)))
        app.start()
        self.assertEqual(self.wait_for(app, 'streaming')['device']['version'], '01.11.00.00')
        app.stop()
        self.wait_for(app, 'idle')
        app._thread.join(5)
        plugged[0], app._checks = False, (0, None)
        self.assertIsNone(app.snapshot()['device'])
        plugged[0], app._checks = True, (0, None)
        app.snapshot()
        app._probe.join(5)
        device = app.snapshot()['device']
        self.assertEqual((device['build'], device['tested']), ('Feb 26 2025', False))

    def test_problems_name_their_recovery(self):
        app = self.app((dict(event='waiting', message=SIMULATOR_SILENT),))
        app.start()
        self.assertEqual(self.wait_for(app, 'waiting')['problem']['code'], 'virtual_flight')
        for message, code in (('Waiting for powered goggles in Virtual Flight mode', 'unplugged'),
                              ('Goggles rejected 0b/1a: d6', 'rejected'), ('USB link is full-speed (12 Mbps)', 'slow_link'),
                              ('Encoded frames repeatedly exceed the size limit. Lower the bitrate', 'oversize'),
                              ('something new', 'other')):
            self.assertEqual(problem_code(message), code)

    def test_failed_capture_check_and_missing_tools_stop_before_usb(self):
        app = self.app(check=lambda settings: 'FFmpeg test encode failed.\n  detail')
        app.start()
        state = self.wait_for(app, 'error')
        self.assertEqual(state['problem'], dict(code='encoder', message='FFmpeg test encode failed.\n  detail'))
        missing = dict(READY, driver=dict(needed=True, ok=False))
        app = self.app(checks=missing)
        self.assertEqual(app.start(), dict(ok=False))
        self.assertEqual(app.snapshot()['problem']['code'], 'driver')
        self.assertIsNone(app._thread)

    def test_options_follow_the_engine_rules_and_persist(self):
        app = self.app()
        # Windows capture, so the bitrate rules are the same on every test host
        self.assertEqual(app.set_options(dict(capture='gfxcapture')), dict(ok=True))
        self.assertIn('at most 24 Mbps', app.set_options(dict(fps=60, bitrate_mbps=40))['error'])
        self.assertEqual(app.snapshot()['options']['fps'], 100)
        self.assertEqual(app.set_options(dict(fps=60, bitrate_mbps=None, display_index=1, unknown=5)), dict(ok=True))
        rates = app.snapshot()['choices']['bitrates']
        self.assertEqual(rates['60'], dict(allowed=[8, 10, 12, 16, 20, 24], auto=24))
        self.assertEqual(rates['100']['auto'], 32)
        self.assertFalse(app.snapshot()['onboarded'])
        app.finish_setup()
        again = self.app()
        self.assertEqual((again._options['fps'], again._options['display_index']), (60, 1))
        self.assertTrue(again.snapshot()['onboarded'])
        self.assertNotIn('unknown', again._options)
        self.settings_path.write_text('{"fps": 61}', encoding='utf-8')
        self.assertEqual(self.app()._options['fps'], 100)


if __name__ == '__main__':
    unittest.main()
