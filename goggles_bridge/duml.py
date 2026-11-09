"""DUML checksums and the Virtual Flight video fragment header.

The PC V1 route and the mobile V2 route share both. See
docs/research/MOBILE_PROTOCOL.md for the header layout.
"""
import binascii
import struct
import time

VIDEO = (0x0B, 0x53)
VIDEO_HEADER_SIZE = 32


def check_uint(value, bits, name):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f'{name} must be an unsigned {bits}-bit integer')


def as_bytes(value):
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError('Expected bytes, bytearray or memoryview')
    return bytes(value)


def _crc_table(polynomial):
    result = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (polynomial if value & 1 else 0)
        result.append(value)
    return tuple(result)


_CRC8 = _crc_table(0x8C)
_REVERSE_BITS = bytes(int(f'{value:08b}'[::-1], 2) for value in range(256))


def crc8(data):
    value = 0x77
    for byte in data:
        value = _CRC8[value ^ byte]
    return value


def crc16(data):
    # crc_hqx uses the same polynomial with the opposite bit order
    value = binascii.crc_hqx(bytes(data).translate(_REVERSE_BITS), 0x496C)
    return (_REVERSE_BITS[value & 255] << 8) | _REVERSE_BITS[value >> 8]


def video_fragments(frame, chunk_size, chunk_id, timestamp_ms=None):
    """Split one nonempty H.264 access unit into payloads that start with the video header.

    The caller supplies encoded bytes and access unit boundaries. Keyframes
    must include codec configuration, as in the app's encoder output. Fragment
    chunk IDs count up from chunk_id.

    Timestamps follow the ARM app: truncate epoch milliseconds to signed
    32 bits, then sign-extend to 64 bits. Without a timestamp override, sample
    the clock for each fragment.
    """
    frame = as_bytes(frame)
    if not frame:
        raise ValueError('Empty H.264 access unit')
    if timestamp_ms is not None:
        check_uint(timestamp_ms, 63, 'timestamp_ms')
    payloads = []
    for offset in range(0, len(frame), chunk_size):
        chunk = frame[offset:offset+chunk_size]
        milliseconds = time.time_ns()//1_000_000 if timestamp_ms is None else timestamp_ms
        timestamp = ((milliseconds+(1 << 31)) % (1 << 32))-(1 << 31)
        header = struct.pack('<BBBBIqIIB7x', 0, len(frame) > chunk_size, offset+len(chunk) == len(frame), 0,
                             (chunk_id+len(payloads)) & 0xFFFFFFFF, timestamp, VIDEO_HEADER_SIZE, len(chunk),
                             offset == 0)
        payloads.append(header+chunk)
    return payloads
