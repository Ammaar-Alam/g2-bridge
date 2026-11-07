import struct
import unittest
from goggles_bridge.annexb import AccessUnitStream
from goggles_bridge.logiclink import LogicLinkStream
from goggles_bridge.protocol import wrap_logiclink


class StreamTests(unittest.TestCase):
    def test_annexb_all_split_points_keep_configuration(self):
        config_idr = b'\0\0\0\1\x67sps\0\0\1\x68pps\0\0\1\x65idr'
        predictive = b'\0\0\0\1\x41predictive'
        raw = b'\0\0\0\1\x09\xf0' + config_idr + b'\0\0\1\x09\xf0' + predictive
        for split in range(len(raw)+1):
            parser = AccessUnitStream()
            self.assertEqual(parser.feed(raw[:split]) + parser.feed(raw[split:]) + parser.finish(), [config_idr, predictive])

    def test_missing_delimiter_and_bound(self):
        with self.assertRaises(ValueError):
            parser = AccessUnitStream()
            parser.feed(b'\0\0\1\x65data')
            parser.finish()
        with self.assertRaises(ValueError):
            AccessUnitStream(16).feed(b'\0\0\1\x09\xf0\0\0\1\x65' + b'x' * 20)

    def test_logiclink_fragmentation_and_channels(self):
        data = wrap_logiclink(b'command', 0x5749) + struct.pack('<HHI', 0xcc55, 0x7530, 5) + b'reply' + wrap_logiclink(b'video')
        expected = [(0x5749, b'command'), (0x7530, b'reply'), (0x574a, b'video')]
        for split in range(len(data)+1):
            parser = LogicLinkStream()
            self.assertEqual(parser.feed(data[:split]) + parser.feed(data[split:]), expected)

    def test_logiclink_discards_invalid_header(self):
        bad = struct.pack('<HHI', 0xcc55, 0x5749, 0xffffffff)
        parser = LogicLinkStream()
        self.assertEqual(parser.feed(bad + wrap_logiclink(b'good')), [(0x574a, b'good')])
        self.assertEqual(parser.discarded, 8)
