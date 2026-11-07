"""DUML V1 control packets recovered from Virtual Flight's ARM serializer."""
from dataclasses import dataclass
import struct
from .protocol import _bytes, _integer, crc8, crc16


@dataclass(frozen=True)
class V1Packet:
    command_set: int
    command_id: int
    sender_type: int
    sender_id: int
    receiver_type: int
    receiver_id: int
    is_response: int
    ack: int
    sequence: int
    payload: bytes = b''

    def serialize(self):
        for name, bits in (('command_set', 8), ('command_id', 8), ('sender_type', 5),
                           ('sender_id', 3), ('receiver_type', 5), ('receiver_id', 3),
                           ('is_response', 1), ('ack', 2), ('sequence', 16)):
            _integer(getattr(self, name), bits, name)
        payload = _bytes(self.payload)
        length = len(payload) + 13
        if length > 1023:
            raise ValueError('V1 packet exceeds its 10-bit length field')
        header = b'\x55' + struct.pack('<H', length | 0x400)
        data = (header + bytes((crc8(header), self.sender_type | self.sender_id << 5,
                               self.receiver_type | self.receiver_id << 5))
                + struct.pack('<HBBB', self.sequence, self.is_response << 7 | self.ack << 5,
                              self.command_set, self.command_id) + payload)
        return data + struct.pack('<H', crc16(data))

    @classmethod
    def parse(cls, data):
        data = _bytes(data)
        if len(data) < 13 or data[0] != 0x55:
            raise ValueError('Missing V1 header')
        size_version = struct.unpack_from('<H', data, 1)[0]
        if size_version >> 10 != 1 or size_version & 1023 != len(data):
            raise ValueError('V1 version or length mismatch')
        if crc8(data[:3]) != data[3] or crc16(data[:-2]) != struct.unpack_from('<H', data, len(data)-2)[0]:
            raise ValueError('V1 CRC mismatch')
        if data[8] & 31:
            raise ValueError('Unsupported V1 encryption/reserved bits')
        return cls(data[9], data[10], data[4] & 31, data[4] >> 5, data[5] & 31,
                   data[5] >> 5, data[8] >> 7, (data[8] >> 5) & 3,
                   struct.unpack_from('<H', data, 6)[0], data[11:-2])


class V1Stream:
    """Reassemble raw V1 packets across USB reads, rejecting bad checksums."""
    def __init__(self):
        self.buffer = bytearray()
        self.discarded = 0

    def feed(self, data):
        self.buffer.extend(_bytes(data))
        result = []
        while len(self.buffer) >= 4:
            size_version = struct.unpack_from('<H', self.buffer, 1)[0]
            size = size_version & 1023
            if (self.buffer[0] != 0x55 or size_version >> 10 != 1 or size < 13
                    or crc8(self.buffer[:3]) != self.buffer[3]):
                del self.buffer[0]
                self.discarded += 1
                continue
            if len(self.buffer) < size:
                break
            try:
                packet = V1Packet.parse(self.buffer[:size])
            except ValueError:
                del self.buffer[0]
                self.discarded += 1
                continue
            result.append(packet)
            del self.buffer[:size]
        return result


def heartbeat(sequence):
    return V1Packet(0, 0, 2, 0, 0x1c, 0, 0, 2, sequence, bytes.fromhex('000020000000'))


def device_info(sequence):
    return V1Packet(0, 0xff, 2, 0, 0x1c, 1, 0, 2, sequence, b'\0')


def sim_mode(sequence):
    return V1Packet(0x0b, 0x1a, 2, 0, 0x1c, 0, 0, 2, sequence, bytes.fromhex('01010000'))
