import struct
import unittest
from goggles_bridge.control import V1Packet, V1Stream
from goggles_bridge.pc_video import PcVideoPacketizer, MAX_PC_VIDEO_CHUNK
from goggles_bridge.protocol import VideoPacketizer, V2Packet, unwrap_logiclink
from goggles_bridge.session import ControlSession, SessionError, SessionLost


class PcVideoTests(unittest.TestCase):
    def test_native_metadata_is_preserved_for_single_fragment(self):
        data = bytes(range(200))
        native = VideoPacketizer('zv900', chunk_id=8).packetize(data, timestamp_ms=1794000000123)[0]
        original = V2Packet.parse(unwrap_logiclink(native)[1])
        wire, = PcVideoPacketizer(chunk_id=8).packetize(data, lambda: 4, timestamp_ms=1794000000123)
        packet = V1Packet.parse(wire)
        self.assertEqual(packet.payload, original.payload)
        self.assertEqual((packet.sender_type, packet.sender_id, packet.receiver_type, packet.receiver_id), (10, 1, 28, 1))
        self.assertEqual((packet.command_set, packet.command_id, packet.ack), (11, 83, 0))

    def test_fragments_survive_batched_usb_boundaries_and_rollover(self):
        for size in (1, 978, 979, 2000, 41667, 65405):
            with self.subTest(size=size):
                data = bytes(i % 251 for i in range(size))
                control = ControlSession(sequence=65534)
                video = PcVideoPacketizer(chunk_id=0xffffffff)
                packets = video.packetize(data, control.reserve_sequence, timestamp_ms=0x80000000)
                wire = b''.join(packets)
                stream = V1Stream()
                recovered = []
                for offset in range(0, len(wire), 2048):
                    recovered += stream.feed(wire[offset:offset+2048])
                self.assertEqual([p.serialize() for p in recovered], packets)
                self.assertEqual(stream.discarded, 0)
                self.assertEqual(b''.join(p.payload[32:] for p in recovered), data)
                self.assertEqual([p.sequence for p in recovered], [(65534+i)&65535 for i in range(len(packets))])
                for i, packet in enumerate(recovered):
                    self.assertLessEqual(len(packets[i]), 1023)
                    metadata = struct.unpack('<BBBBIqIIB7x', packet.payload[:32])
                    self.assertEqual(metadata, (0, size>MAX_PC_VIDEO_CHUNK, i==len(packets)-1, 0,
                        (0xffffffff+i)&0xffffffff, -0x80000000, 32, len(packet.payload)-32, i==0))

    def test_video_sequence_skips_pending_control_requests(self):
        control = ControlSession(sequence=65535)
        request, = control.poll(0)
        control.sequence = request.sequence
        wire, = PcVideoPacketizer().packetize(b'frame', control.reserve_sequence, timestamp_ms=0)
        self.assertEqual(V1Packet.parse(wire).sequence, 0)
        self.assertIn(65535, control.pending)
        with self.assertRaises(SessionLost):
            control.poll(4)
        with self.assertRaises(SessionError):
            control.reserve_sequence()

    def test_invalid_input_keeps_counter(self):
        for frame, timestamp in ((b'', 0), (b'a', -1), (b'a', 1.5), (b'a', 1<<63)):
            video = PcVideoPacketizer(chunk_id=7)
            with self.assertRaises(ValueError):
                video.packetize(frame, lambda: 0, timestamp_ms=timestamp)
            self.assertEqual(video.chunk_id, 7)
