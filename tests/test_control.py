from dataclasses import replace
import json
from pathlib import Path
import unittest
from goggles_bridge.control import V1Packet, V1Stream, heartbeat, device_info, sim_mode


class ControlTests(unittest.TestCase):
    def test_native_oracles(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/v1-oracle.json').read_text())
        for case in fixture['cases']:
            with self.subTest(case=case['name']):
                packet = V1Packet(**case['fields'], payload=bytes.fromhex(case['payload_hex']))
                self.assertEqual(packet.serialize().hex(), case['packet_hex'])
                self.assertEqual(V1Packet.parse(bytes.fromhex(case['packet_hex'])), packet)
                if case['name'] in ('heartbeat', 'device_info', 'sim_mode'):
                    # the oracle uses the app's own address; the bridge sends from the PC address
                    request = globals()[case['name']](4660)
                    self.assertEqual((request.sender_type, request.sender_id), (10, 1))
                    self.assertEqual(replace(request, sender_type=2, sender_id=0), packet)

    def test_real_receive_and_fragmentation(self):
        raw = bytes.fromhex('550e04660e2ac701000943033039')
        packet = V1Packet.parse(raw)
        self.assertEqual((packet.command_set, packet.command_id, packet.payload), (9, 0x43, b'\x03'))
        for split in range(len(raw) + 1):
            decoder = V1Stream()
            result = decoder.feed(raw[:split]) + decoder.feed(raw[split:])
            self.assertEqual(result, [packet])

    def test_resynchronization(self):
        raw = heartbeat(3).serialize()
        corrupt = raw[:-1] + bytes((raw[-1] ^ 1,))
        stream = V1Stream()
        self.assertEqual(stream.feed(b'noise' + corrupt + raw + raw), [heartbeat(3), heartbeat(3)])
        self.assertEqual(stream.discarded, 5 + len(corrupt))

    def test_reject_invalid(self):
        packet = heartbeat(0)
        fields = dict(packet.__dict__)
        for change in ({'sender_type': 32}, {'ack': 4}, {'payload': b'x' * 1011}):
            with self.assertRaises(ValueError):
                V1Packet(**(fields | change)).serialize()
        raw = packet.serialize()
        for bad in (raw[:-1], raw + b'\0', raw[:3] + b'\0' + raw[4:]):
            with self.assertRaises(ValueError):
                V1Packet.parse(bad)
