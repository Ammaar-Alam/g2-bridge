from dataclasses import replace
from pathlib import Path
import queue
import tempfile
import threading
import unittest

from goggles_bridge.control import V1Stream
from goggles_bridge.engine import BridgeEngine, BridgeSettings, encoder_command
from goggles_bridge.session import SessionError
from goggles_bridge.windows_usb import DeviceNotFoundError, UsbTransportError


class EncoderOutput:
    def __init__(self, stopped, eof=False):
        self.stopped = stopped
        self.first = True
        self.eof = eof

    def read(self, _size):
        if self.eof:
            return b''
        if self.first:
            self.first = False
            return (b'\0\0\0\1\x09\xf0\0\0\0\1\x65test-picture')*3
        self.stopped.wait(2)
        return b''

    def close(self):
        pass


class FakeEncoder:
    pid = 123

    def __init__(self, eof=False):
        self.stopped = threading.Event()
        self.stdout = EncoderOutput(self.stopped, eof)
        self.terminated = False

    def poll(self):
        return 0 if self.stopped.is_set() else None

    def terminate(self):
        self.terminated = True
        self.stopped.set()

    def wait(self, timeout):
        return 0


class FakeUsb:
    def __init__(self, stop, *, wrong_model=False, disconnect=False):
        self.stop = stop
        self.wrong_model = wrong_model
        self.disconnect = disconnect
        self.incoming = queue.Queue()
        self.decoder = V1Stream()
        self.video = []
        self.mode = False
        self.closed = False

    def write(self, data):
        for request in self.decoder.feed(data):
            command = request.command_set, request.command_id
            if command == (11, 83):
                if not self.mode:
                    raise AssertionError('Video arrived before simulator acknowledgement')
                if self.disconnect:
                    raise UsbTransportError('Unplugged during video')
                self.video.append(request)
                self.stop.set()
                continue
            payload = b'\0'
            if command == (0, 255):
                payload += b'E3T ZV902' if self.wrong_model else b'E3T ZV900 AC'
            if command == (11, 26):
                self.mode = True
            response = replace(request, sender_type=request.receiver_type, sender_id=request.receiver_id,
                receiver_type=request.sender_type, receiver_id=request.sender_id, is_response=1, ack=2, payload=payload)
            self.incoming.put(response.serialize())

    def read(self, timeout_ms):
        try:
            return self.incoming.get(timeout=timeout_ms/1000)
        except queue.Empty:
            return b''

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


class EngineTests(unittest.TestCase):
    def settings(self, **kwargs):
        return BridgeSettings(Path('driver.dll'), Path('ffmpeg.exe'), **kwargs)

    def run_case(self, factory, stop, *, encoder_factory=None):
        events, encoders = [], []
        def create_encoder(*args, **kwargs):
            encoder = encoder_factory() if encoder_factory else FakeEncoder()
            encoders.append(encoder)
            return encoder
        with tempfile.TemporaryDirectory() as folder:
            engine = BridgeEngine(self.settings(), Path(folder)/'run.jsonl', stop_event=stop,
                on_event=events.append, transport_factory=factory, process_factory=create_encoder,
                retry_delay=.001, duration=2)
            engine.run()
        return events, encoders

    def test_handshake_video_and_stop_release_owned_resources(self):
        stop = threading.Event()
        usb = FakeUsb(stop)
        events, encoders = self.run_case(lambda _: usb, stop)
        self.assertTrue(usb.closed)
        self.assertTrue(usb.video)
        self.assertTrue(encoders[0].terminated)
        names = [r['event'] for r in events]
        self.assertLess(names.index('ready'), names.index('streaming'))
        self.assertEqual(names[-1], 'stopped')

    def test_disconnect_restarts_both_handshake_and_encoder(self):
        stop = threading.Event()
        devices = [FakeUsb(stop, disconnect=True), FakeUsb(stop)]
        calls = []
        def factory(_):
            result = devices[len(calls)]
            calls.append(result)
            return result
        events, encoders = self.run_case(factory, stop)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(d.closed for d in devices))
        self.assertTrue(all(p.terminated for p in encoders))
        self.assertEqual(sum(e['event']=='ready' for e in events), 2)
        self.assertTrue(any(e['event']=='waiting' for e in events))

    def test_absent_device_can_be_stopped_while_waiting(self):
        stop = threading.Event()
        def missing(_):
            stop.set()
            raise DeviceNotFoundError('No goggles')
        events, encoders = self.run_case(missing, stop)
        self.assertEqual(encoders, [])
        self.assertEqual(events[-1]['event'], 'stopped')

    def test_wrong_model_is_fatal_and_never_starts_encoder(self):
        stop = threading.Event()
        usb = FakeUsb(stop, wrong_model=True)
        with self.assertRaises(SessionError):
            self.run_case(lambda _: usb, stop, encoder_factory=lambda: self.fail('Must not encode'))
        self.assertTrue(usb.closed)
        self.assertFalse(usb.video)

    def test_encoder_eof_is_fatal_and_releases_usb(self):
        stop = threading.Event()
        usb = FakeUsb(stop)
        with self.assertRaisesRegex(RuntimeError, 'Capture ended'):
            self.run_case(lambda _: usb, stop, encoder_factory=lambda: FakeEncoder(eof=True))
        self.assertTrue(usb.closed)

    def test_gpu_capture_preserves_verified_encoder_contract(self):
        command = encoder_command(self.settings())
        source = command[command.index('-i')+1]
        self.assertIn('scale_aspect', source)
        self.assertNotIn('-vf', command)
        for key, value in (('-r','100'), ('-level:v','5.1'), ('-bf','0'), ('-aud','1'), ('-bufsize','400000')):
            self.assertEqual(command[command.index(key)+1], value)
        command = encoder_command(self.settings(fps=60, capture='ddagrab'))
        self.assertEqual(command[command.index('-level:v')+1], '4.2')
        self.assertIn('force_original_aspect_ratio=decrease', command[command.index('-vf')+1])
