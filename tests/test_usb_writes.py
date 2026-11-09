from itertools import count
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from goggles_bridge.control import V1Stream
from goggles_bridge.engine import BridgeEngine, BridgeSettings
from goggles_bridge.pc_video import PcVideoPacketizer
from goggles_bridge.usb_transport import ControlUsb, UsbTransportError, USB_WRITE_SIZES


class DriverError(Exception):
    pass


class UsbWriteTests(unittest.TestCase):
    def transport(self, write_size, *, fail=None):
        writes = []
        def write(endpoint, data, timeout):
            self.assertEqual((endpoint, timeout), (4, 500))
            writes.append(bytes(data))
            if fail == 'error':
                raise DriverError('disconnected')
            return len(data)-(1 if fail == 'short' else 0)
        usb = ControlUsb.__new__(ControlUsb)
        usb.device = SimpleNamespace(write=write)
        usb.link = SimpleNamespace(interface=4, endpoint_out=4, endpoint_in=0x85, packet_size=512, product_id=0x20)
        usb.core = SimpleNamespace(USBError=DriverError)
        usb.closed = False
        usb.write_size = write_size
        return usb, writes

    def test_transfer_boundaries_preserve_packet_bytes_and_frame(self):
        frame = bytes(range(256))*101
        packets = PcVideoPacketizer().packetize(frame, count().__next__, timestamp_ms=123456)
        wire = b''.join(p.serialize() for p in packets)
        calls = []
        for size in USB_WRITE_SIZES:
            with self.subTest(write_size=size):
                usb, writes = self.transport(size)
                usb.write(memoryview(wire))
                self.assertEqual(b''.join(writes), wire)
                self.assertTrue(all(len(data)==size for data in writes[:-1]))
                self.assertLessEqual(len(writes[-1]), size)
                reader = V1Stream()
                delivered = [packet for data in writes for packet in reader.feed(data)]
                self.assertEqual(b''.join(p.payload[32:] for p in delivered), frame)
                self.assertEqual(reader.discarded, 0)
                self.assertFalse(reader.buffer)
                calls.append(len(writes))
        self.assertEqual(calls, [14, 2])

    def test_short_write_and_disconnect_stop_without_sending_remaining_bytes(self):
        for size in USB_WRITE_SIZES:
            for failure in ('short', 'error'):
                with self.subTest(write_size=size, failure=failure):
                    usb, writes = self.transport(size, fail=failure)
                    with self.assertRaises(UsbTransportError):
                        usb.write(b'x'*(size+1))
                    self.assertEqual(len(writes), 1)

    def test_closed_transport_does_not_write(self):
        usb, writes = self.transport(16384)
        usb.closed = True
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            usb.write(b'x')
        self.assertEqual(writes, [])

    def test_rejects_invalid_sizes_before_loading_driver(self):
        for value in (0, -1, True, 2048.0, 4096, 65536):
            with self.subTest(write_size=value):
                with self.assertRaises(ValueError):
                    ControlUsb('unused.dll', write_size=value)
                with self.assertRaises(ValueError):
                    BridgeSettings(Path('unused.dll'), Path('unused.exe'), usb_write_size=value)

    def test_engine_passes_size_to_default_transport_on_every_connection(self):
        settings = BridgeSettings(Path('unused.dll'), Path('unused.exe'), usb_write_size=16384)
        with patch('goggles_bridge.engine.ControlUsb') as constructor:
            engine = BridgeEngine(settings, Path('unused.jsonl'))
            for _ in range(2):
                engine.transport_factory(settings.dll)
            self.assertEqual(constructor.call_count, 2)
            constructor.assert_called_with(settings.dll, write_size=16384)


if __name__ == '__main__':
    unittest.main()
