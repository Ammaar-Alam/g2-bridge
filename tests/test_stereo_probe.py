import json
from pathlib import Path
import tempfile
import unittest

from goggles_bridge.control import V1Packet, heartbeat
from goggles_bridge.engine import BridgeSettings, encoder_command
from tools.research import stereo_probe


class StereoProbeTests(unittest.TestCase):
    def test_command_keeps_bridge_encoder_and_replaces_source(self):
        settings = BridgeSettings(Path('dll'), Path('ffmpeg'), fps=60)
        bridge = encoder_command(settings)
        for layout, size in (('sbs', '960x1080'), ('fsbs', '1920x1080'), ('ftb', '1920x1080')):
            with self.subTest(layout=layout):
                command = stereo_probe.probe_command(settings, layout)
                source = command[command.index('-i')+1]
                self.assertIn(f'testsrc2=size={size}:rate=60', source)
                self.assertIn('vstack' if layout == 'ftb' else 'hstack', source)
                self.assertEqual(command[command.index('-level:v')+1], '5.1')
                self.assertEqual(command[-3:], bridge[-3:])
                self.assertEqual(len(command), len(bridge))

    def test_inbound_summary_reassembles_split_reads(self):
        push = V1Packet(0x09, 0x43, 14, 0, 10, 1, 0, 0, 7, b'\x03').serialize()
        reply = V1Packet(0, 0, 28, 0, 10, 1, 1, 0, 1, bytes(7)).serialize()
        rows = [{'event': 'control_send', 'hex': heartbeat(1).serialize().hex()},
                {'event': 'control_receive', 'hex': (push + reply[:5]).hex()},
                {'event': 'control_receive', 'hex': (reply[5:] + push).hex()}]
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'log.jsonl'
            log.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
            self.assertEqual(stereo_probe.inbound_summary(log), {(9, 0x43, 14, 0): 2, (0, 0, 28, 0): 1})


if __name__ == '__main__':
    unittest.main()
