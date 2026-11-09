import unittest
from goggles_bridge.annexb import AccessUnitStream


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
