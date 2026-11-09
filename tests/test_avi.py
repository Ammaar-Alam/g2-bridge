import struct
import unittest
from goggles_bridge.avi import AviPacketStream
from goggles_bridge.annexb import AccessUnitStream, strip_aud
from avi_fixture import chunk, header, stream

AUD = b'\0\0\0\1\x09\xf0'
PACKETS = [AUD+b'\0\0\0\1\x67sps\0\0\1\x68pps\0\0\1\x65idr',
           AUD+b'\0\0\1\x41frame', AUD+b'\0\0\1\x41other']
FRAMES = [strip_aud(packet) for packet in PACKETS]


class AviTests(unittest.TestCase):
    def test_every_split_point_preserves_packets(self):
        data = stream(PACKETS)
        for cut in range(len(data)+1):
            parser = AviPacketStream()
            self.assertEqual(parser.feed(data[:cut])+parser.feed(data[cut:]), FRAMES)
            parser.finish()

    def test_frame_is_available_without_next_delimiter_or_pad(self):
        packet = AUD+b'\0\0\1\x65odd'
        self.assertEqual(len(packet)&1, 1)
        parser = AviPacketStream()
        self.assertEqual(parser.feed(header()+chunk(b'00dc', packet)[:-1]), [strip_aud(packet)])
        baseline = AccessUnitStream()
        self.assertEqual(baseline.feed(packet), [])
        self.assertEqual(baseline.feed(PACKETS[1]), [strip_aud(packet)])
        self.assertEqual(parser.feed(b'\0'), [])
        parser.finish()

    def test_metadata_and_empty_repeat_chunks_are_not_video(self):
        data = header()+chunk(b'00dc', b'')+chunk(b'JUNK', b'xyz')+chunk(b'00dc', PACKETS[0])+chunk(b'idx1', b'')
        parser = AviPacketStream()
        self.assertEqual(parser.feed(data), FRAMES[:1])
        parser.finish()

    def test_wrong_codec_and_multiple_streams_are_rejected(self):
        for data in (stream(PACKETS).replace(b'vidsH264', b'audsH264'),
                     stream(PACKETS).replace(b'H264', b'HEVC'),
                     stream(PACKETS).replace(b'AVI ', b'WAVE', 1)):
            with self.assertRaises(ValueError):
                AviPacketStream().feed(data)
        data = bytearray(stream(PACKETS))
        struct.pack_into('<I', data, data.index(b'avih')+8+24, 2)
        with self.assertRaisesRegex(ValueError, 'one AVI'):
            AviPacketStream().feed(data)

    def test_oversized_and_truncated_chunks_fail_with_bounded_buffers(self):
        parser = AviPacketStream(max_frame_bytes=64)
        with self.assertRaisesRegex(ValueError, 'bound'):
            parser.feed(header()+b'00dc'+struct.pack('<I', 2**31))
        parser = AviPacketStream()
        with self.assertRaisesRegex(ValueError, 'bound'):
            parser.feed(b'RIFF\xff\xff\xff\xffAVI JUNK'+struct.pack('<I', 2**31))
        for data in (b'RIFF', header()[:-1], stream(PACKETS)[:-2]):
            parser = AviPacketStream()
            parser.feed(data)
            with self.assertRaisesRegex(ValueError, 'Truncated'):
                parser.finish()

    def test_single_access_unit_check_retains_all_picture_nals(self):
        baseline = AccessUnitStream()
        expected = baseline.feed(b''.join(PACKETS))+baseline.finish()
        self.assertEqual(FRAMES, expected)
        for data in (b'', AUD, b'no delimiter', PACKETS[0]+PACKETS[1]):
            with self.assertRaises(ValueError):
                strip_aud(data)
