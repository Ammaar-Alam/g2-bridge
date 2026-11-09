from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from goggles_bridge.control import V1Stream
from goggles_bridge.engine import BridgeEngine, BridgeSettings, MAX_FRAME_BYTES
from test_engine import AUD, EncoderOutput, FakeEncoder, FakeUsb


class RecoveryOutput(EncoderOutput):
    def __init__(self, process, packets, needs_close=False):
        super().__init__(process.stopped, framed=True, packets=packets)
        self.needs_close = needs_close
        self.closed = False
        self.waiting = threading.Event()
        self.pipe_closed = threading.Event()

    def read(self, size):
        if self.first or not self.needs_close:
            return super().read(size)
        self.waiting.set()
        self.pipe_closed.wait(3)
        return b''

    def close(self):
        self.closed = True
        self.pipe_closed.set()


class RecoveryUsb(FakeUsb):
    def __init__(self, stop):
        super().__init__(threading.Event())
        self.actual_stop = stop
        self.audit = V1Stream()
        self.commands, self.sequences = [], []

    def write(self, data):
        super().write(data)
        for packet in self.audit.feed(data):
            self.sequences.append(packet.sequence)
            self.commands.append((packet.command_set, packet.command_id))
            if (packet.command_set, packet.command_id) == (11, 83) and b'after' in packet.payload:
                self.actual_stop.set()


class EncoderRecoveryTests(unittest.TestCase):
    def test_recovery_preserves_usb_and_closes_every_encoder(self):
        idr, inter = AUD + b'\0\0\0\1\x65', AUD + b'\0\0\0\1\x41'
        oversized = inter + bytes(MAX_FRAME_BYTES+1)
        recovered = [idr+b'recovered', inter+b'after']
        cases = {
            'midstream': ([[idr+b'first', oversized, inter+b'old'], [inter+b'old', *recovered]], 3, None),
            'startup': ([[oversized], recovered], 2, None),
            'repeated': ([[oversized]]*3, 0, RuntimeError),
            'repeated_after_idr': ([[idr+b'first', oversized]]*3, 3, RuntimeError),
            'start_failure': ([[oversized], None], 0, OSError),
            'stop_during_restart': ([[oversized]], 0, None),
            'kill_fallback': ([[oversized], recovered], 2, None),
            'pipe_close_unblocks': ([[oversized], recovered], 2, None),
        }
        for name, (generations, expected, error_type) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as folder:
                stop = threading.Event()
                usb = RecoveryUsb(stop)
                processes, events, opens = [], [], []

                def factory(*args, **kwargs):
                    packets = generations[len(processes)]
                    if packets is None:
                        raise OSError('Test encoder startup failure')
                    process = FakeEncoder(framed=True)
                    process.stdout = RecoveryOutput(process, packets, name == 'pipe_close_unblocks')
                    if name == 'kill_fallback':
                        def terminate():
                            process.terminated = True
                        def wait(timeout):
                            if not process.stopped.is_set():
                                raise subprocess.TimeoutExpired('test-encoder', timeout)
                            return 0
                        def kill():
                            process.killed = True
                            process.stopped.set()
                        process.terminate, process.wait, process.kill = terminate, wait, kill
                    processes.append(process)
                    return process

                def transport(_):
                    opens.append(True)
                    return usb

                def event(row):
                    events.append(row)
                    if row['event'] == 'oversize_frame':
                        if name == 'stop_during_restart':
                            stop.set()
                        if name == 'pipe_close_unblocks':
                            self.assertTrue(processes[-1].stdout.waiting.wait(.5))

                engine = BridgeEngine(BridgeSettings(None, Path('unused.exe')), Path(folder)/'run.jsonl',
                    duration=1, reconnect=False, stop_event=stop, transport_factory=transport,
                    process_factory=factory, on_event=event)
                if error_type:
                    with self.assertRaises(error_type):
                        engine.run()
                else:
                    engine.run()
                self.assertEqual(len(usb.video), expected)
                self.assertEqual(len(opens), 1)
                self.assertEqual(usb.commands.count((11, 26)), 1)
                self.assertEqual(len(usb.sequences), len(set(usb.sequences)))
                self.assertTrue(all(p.terminated and p.stdout.closed for p in processes))
                self.assertTrue(usb.closed)
                self.assertEqual(events[-1]['event'], 'stopped')
                self.assertFalse(any(b'old' in packet.payload for packet in usb.video))
                self.assertTrue(all(len(packet.payload) < MAX_FRAME_BYTES for packet in usb.video))
                if name in ('repeated', 'repeated_after_idr'):
                    self.assertEqual(len(processes), 3)
                if name == 'kill_fallback':
                    self.assertTrue(all(p.killed for p in processes))
