import random
import unittest
from goggles_bridge.duml import crc16


def bitwise_crc(data):
    value = 0x3692
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0x8408 if value & 1 else 0)
    return value


class FastCrcTests(unittest.TestCase):
    def test_bit_reflection_matches_independent_bitwise_reference(self):
        rng = random.Random(47)
        samples = [b'', bytes(range(256))]+[bytes((x,)) for x in range(256)]
        samples += [rng.randbytes(n) for n in (13, 31, 978, 1021, 2048, 65404)]
        for data in samples:
            self.assertEqual(crc16(data), bitwise_crc(data))
        for data in (bytearray(b'buffer'), memoryview(b'buffer')):
            self.assertEqual(crc16(data), bitwise_crc(data))
