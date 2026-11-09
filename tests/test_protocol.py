import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from goggles_bridge.duml import crc8, crc16
from goggles_bridge.protocol import (
    Address, MAX_VIDEO_CHUNK, PROFILES, V2Packet, VideoPacketizer, unwrap_logiclink, wrap_logiclink,
)

FIXTURES = Path(__file__).parent / 'fixtures'


class ProtocolTests(unittest.TestCase):
    def test_compiled_serializer_vectors(self):
        oracle = json.loads((FIXTURES / 'serializer-oracle.json').read_text())
        for case in oracle['cases']:
            with self.subTest(case=case['name']):
                f = case['fields']
                packet = V2Packet(f['command_set'], f['command_id'],
                                  Address(f['sender_type'], f['sender_id'], f['sender_index']),
                                  Address(f['receiver_type'], f['receiver_id'], f['receiver_index']),
                                  f['ack'], f['sequence'], bytes.fromhex(case['payload_hex']))
                expected = bytes.fromhex(case['packet_hex'])
                self.assertEqual(packet.serialize(), expected)
                self.assertEqual(V2Packet.parse(expected), packet)

    def test_compiled_video_fragment_vectors(self):
        oracle = json.loads((FIXTURES / 'video-oracle.json').read_text())
        for case in oracle['cases']:
            with self.subTest(length=case['length']):
                frame = bytes(i % 256 for i in range(case['length']))
                encoder = VideoPacketizer('zv900', sequence=0xFFFFFFFE,
                                          chunk_id=case['initial_chunk_id'])
                packets = encoder.packetize(frame, timestamp_ms=case['milliseconds'])
                self.assertEqual(len(packets), len(case['packets']))
                recovered = bytearray()
                for i, (wire, expected) in enumerate(zip(packets, case['packets'])):
                    channel, inner = unwrap_logiclink(wire)
                    self.assertEqual(channel, 0x574A)
                    self.assertEqual(wire[:8], struct.pack('<HHI', 0xCC55, 0x574A, len(inner)))
                    packet = V2Packet.parse(inner)
                    self.assertEqual(packet.sequence, (0xFFFFFFFE+i) & 0xFFFFFFFF)
                    self.assertEqual(packet.payload[:32].hex(), expected['header_hex'])
                    self.assertEqual(len(packet.payload)-32, expected['data_length'])
                    self.assertEqual(hashlib.sha256(packet.payload[32:]).hexdigest(), expected['data_sha256'])
                    self.assertEqual((packet.command_set, packet.command_id, packet.ack), (11,83,3))
                    self.assertEqual(packet.receiver, PROFILES['zv900'].receiver)
                    recovered.extend(packet.payload[32:])
                self.assertEqual(recovered, frame)
                self.assertEqual(encoder.sequence, (0xFFFFFFFE+len(packets)) & 0xFFFFFFFF)
                self.assertEqual(encoder.chunk_id, encoder.sequence)

    def test_unwrapped_pigeon_and_state_across_frames(self):
        encoder = VideoPacketizer('pigeon', sequence=5, chunk_id=8)
        first = V2Packet.parse(encoder.packetize(b'first', timestamp_ms=0)[0])
        second = V2Packet.parse(encoder.packetize(b'second', timestamp_ms=1)[0])
        self.assertEqual(first.receiver, Address(14,1,0x701))
        self.assertEqual((first.sequence, second.sequence), (5,6))
        self.assertEqual(struct.unpack_from('<I', second.payload, 4)[0],9)
        self.assertEqual(second.payload[:4],b'\x00\x00\x01\x00')
        self.assertEqual(second.payload[24],1)

    def test_clock_sampled_per_fragment_and_signed_timestamp_wrap(self):
        encoder = VideoPacketizer('pigeon')
        with patch('goggles_bridge.duml.time.time_ns', side_effect=[0x7FFFFFFF*1_000_000, 0x80000000*1_000_000]):
            packets = encoder.packetize(b'x'*(MAX_VIDEO_CHUNK+1))
        timestamps = [struct.unpack_from('<q',V2Packet.parse(p).payload,8)[0] for p in packets]
        self.assertEqual(timestamps,[0x7FFFFFFF,-0x80000000])

    def test_payload_limit_and_invalid_fields(self):
        packet = V2Packet(11,83,Address(2,0,257),Address(28,1,2304),3,0,b'x'*65506)
        self.assertEqual(len(packet.serialize()),65535)
        with self.assertRaises(ValueError):
            V2Packet(11,83,packet.sender,packet.receiver,3,0,b'x'*65507).serialize()
        for values in [(-1,0,0),(256,0,0),(0,256,0),(0,0,65536)]:
            with self.assertRaises(ValueError):
                Address(*values)
        for name,value in [('command_set',256),('command_id',-1),('ack',8),('sequence',1<<32)]:
            args = dict(command_set=11,command_id=83,sender=packet.sender,
                        receiver=packet.receiver,ack=3,sequence=0)
            args[name] = value
            with self.subTest(field=name), self.assertRaises(ValueError):
                V2Packet(**args).serialize()

    def test_invalid_video_does_not_advance_counters(self):
        encoder = VideoPacketizer('zv900',sequence=17,chunk_id=21)
        for frame, timestamp in [(b'',0),(b'x',1<<63),(b'x',1.5)]:
            with self.assertRaises(ValueError):
                encoder.packetize(frame,timestamp_ms=timestamp)
        with self.assertRaises(TypeError):
            encoder.packetize('not bytes')
        self.assertEqual((encoder.sequence,encoder.chunk_id),(17,21))
        with self.assertRaises(ValueError):
            VideoPacketizer('goggles2')

    def test_corrupt_and_truncated_packets_rejected(self):
        good = VideoPacketizer('pigeon').packetize(b'test',timestamp_ms=0)[0]
        for index in [0,3,7,23,28,len(good)-1]:
            bad = bytearray(good)
            bad[index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                V2Packet.parse(bad)
        for size in range(len(good)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                V2Packet.parse(good[:size])
        with self.assertRaises(ValueError):
            V2Packet.parse(good+b'\x00')

    def test_unsupported_reserved_field_with_valid_crc_rejected(self):
        bad = bytearray(VideoPacketizer('pigeon').packetize(b'test',timestamp_ms=0)[0])
        bad[11] = 1
        bad[23] = crc8(bad[:23])
        bad[-2:] = struct.pack('<H',crc16(bad[:-2]))
        with self.assertRaisesRegex(ValueError,'reserved'):
            V2Packet.parse(bad)

    def test_logiclink_length_and_channel_validation(self):
        packet = VideoPacketizer('pigeon').packetize(b'test',timestamp_ms=0)[0]
        wrapped = wrap_logiclink(packet)
        for bad in [wrapped[:7],wrapped[:-1],wrapped+b'\x00',b'\x00'+wrapped[1:]]:
            with self.assertRaises(ValueError):
                unwrap_logiclink(bad)
        with self.assertRaises(ValueError):
            wrap_logiclink(packet,0)


if __name__ == '__main__':
    unittest.main()
