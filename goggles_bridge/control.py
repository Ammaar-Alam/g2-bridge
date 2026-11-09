"""DUML V1 control packets recovered from Virtual Flight's ARM serializer."""
from dataclasses import dataclass
import struct
from .duml import as_bytes, check_uint, crc8, crc16

V1_OVERHEAD = 13
V1_MAX_LENGTH = 1023
# (device type, device ID) of the computer on the PC USB route, and the goggles' device type
PC = (10, 1)
GOGGLES = 0x1C
# (command set, command ID)
HEARTBEAT = (0x00, 0x00)
DEVICE_INFO = (0x00, 0xFF)
SIM_MODE = (0x0B, 0x1A)


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

    @property
    def command(self):
        return self.command_set, self.command_id

    def serialize(self):
        for name, bits in (('command_set', 8), ('command_id', 8), ('sender_type', 5),
                           ('sender_id', 3), ('receiver_type', 5), ('receiver_id', 3),
                           ('is_response', 1), ('ack', 2), ('sequence', 16)):
            check_uint(getattr(self, name), bits, name)
        payload = as_bytes(self.payload)
        length = len(payload) + V1_OVERHEAD
        if length > V1_MAX_LENGTH:
            raise ValueError('V1 packet exceeds its 10-bit length field')
        header = b'\x55' + struct.pack('<H', length | 0x400)
        data = (header + bytes((crc8(header), self.sender_type | self.sender_id << 5,
                               self.receiver_type | self.receiver_id << 5))
                + struct.pack('<HBBB', self.sequence, self.is_response << 7 | self.ack << 5,
                              self.command_set, self.command_id) + payload)
        return data + struct.pack('<H', crc16(data))

    @classmethod
    def parse(cls, data):
        data = as_bytes(data)
        if len(data) < V1_OVERHEAD or data[0] != 0x55:
            raise ValueError('Missing V1 header')
        size_version = struct.unpack_from('<H', data, 1)[0]
        if size_version >> 10 != 1 or size_version & V1_MAX_LENGTH != len(data):
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
        self.buffer.extend(as_bytes(data))
        result = []
        while len(self.buffer) >= 4:
            size_version = struct.unpack_from('<H', self.buffer, 1)[0]
            size = size_version & V1_MAX_LENGTH
            if (self.buffer[0] != 0x55 or size_version >> 10 != 1 or size < V1_OVERHEAD
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
    return V1Packet(*HEARTBEAT, *PC, GOGGLES, 0, 0, 2, sequence, bytes.fromhex('000020000000'))


def device_info(sequence):
    return V1Packet(*DEVICE_INFO, *PC, GOGGLES, 1, 0, 2, sequence, b'\0')


def sim_mode(sequence):
    return V1Packet(*SIM_MODE, *PC, GOGGLES, 0, 0, 2, sequence, bytes.fromhex('01010000'))
