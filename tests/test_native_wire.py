import hashlib
import json
from pathlib import Path
import unittest
from goggles_bridge.protocol import VideoPacketizer, unwrap_logiclink


class NativeWireTests(unittest.TestCase):
    def test_complete_native_send_pipeline(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/video-wire-oracle.json').read_text())
        for case in fixture['cases']:
            with self.subTest(length=case['length'], wrapped=case['logiclink']):
                data = bytes(i % 256 for i in range(case['length']))
                packets = VideoPacketizer('zv900').packetize(data, timestamp_ms=1794000000123)
                if not case['logiclink']:
                    packets = [unwrap_logiclink(packet)[1] for packet in packets]
                self.assertEqual(len(packets), case['packets'])
                self.assertEqual(hashlib.sha256(b''.join(packets)).hexdigest(), case['sha256'])
