"""Packet formats recovered from the Android Virtual Flight application.

See docs/research/MOBILE_PROTOCOL.md for layouts and native addresses.
"""
from dataclasses import dataclass
import struct
from .duml import VIDEO, as_bytes, check_uint, crc8, crc16, video_fragments

MAX_VIDEO_CHUNK = 65404
V2_OVERHEAD = 29
LOGIC_COMMAND_CHANNEL = 0x5749
LOGIC_VIDEO_CHANNEL = 0x574A


@dataclass(frozen=True)
class Address:
    device_type: int
    device_id: int
    index: int

    def __post_init__(self):
        check_uint(self.device_type, 8, 'device_type')
        check_uint(self.device_id, 8, 'device_id')
        check_uint(self.index, 16, 'index')

    def pack(self):
        return struct.pack('<IH', self.device_id << 8 | self.device_type << 16, self.index)


VIDEO_SENDER = Address(2, 0, 0x0101)


@dataclass(frozen=True)
class V2Packet:
    command_set: int
    command_id: int
    sender: Address
    receiver: Address
    ack: int
    sequence: int
    payload: bytes = b''

    def serialize(self):
        check_uint(self.command_set, 8, 'command_set')
        check_uint(self.command_id, 8, 'command_id')
        check_uint(self.ack, 3, 'ack')
        check_uint(self.sequence, 32, 'sequence')
        payload = as_bytes(self.payload)
        length = V2_OVERHEAD + len(payload)
        if length > 65535:
            raise ValueError('V2 packet exceeds its 16-bit length field')
        header = (b'\x55\x18\x08' + struct.pack('<HHI', length, self.ack << 5, self.sequence)
                  + self.sender.pack() + self.receiver.pack())
        packet = header + bytes((crc8(header), self.command_set, self.command_id, 0)) + payload
        return packet + struct.pack('<H', crc16(packet))

    @classmethod
    def parse(cls, data):
        """Validate one complete packet in the recovered V2 layout."""
        data = as_bytes(data)
        if len(data) < V2_OVERHEAD or data[:3] != b'\x55\x18\x08':
            raise ValueError('Missing or unsupported V2 header')
        length, flags, sequence = struct.unpack_from('<HHI', data, 3)
        if length != len(data):
            raise ValueError('V2 length mismatch')
        if crc8(data[:23]) != data[23]:
            raise ValueError('V2 header CRC mismatch')
        if crc16(data[:-2]) != struct.unpack_from('<H', data, len(data)-2)[0]:
            raise ValueError('V2 packet CRC mismatch')
        if flags & ~0xE0 or any(data[i] for i in (11, 14, 17, 20, 26)):
            raise ValueError('Unsupported V2 reserved fields')
        sender = Address(data[13], data[12], struct.unpack_from('<H', data, 15)[0])
        receiver = Address(data[19], data[18], struct.unpack_from('<H', data, 21)[0])
        return cls(data[24], data[25], sender, receiver, flags >> 5, sequence, data[27:-2])


def wrap_logiclink(packet, channel=LOGIC_VIDEO_CHANNEL):
    """Add the app's eight-byte LogicLink header."""
    if channel not in (LOGIC_COMMAND_CHANNEL, LOGIC_VIDEO_CHANNEL):
        raise ValueError('Unsupported LogicLink channel')
    packet = as_bytes(packet)
    if len(packet) > 65535:
        raise ValueError('Inner packet exceeds the recovered V2 limit')
    return struct.pack('<HHI', 0xCC55, channel, len(packet)) + packet


def unwrap_logiclink(data):
    data = as_bytes(data)
    if len(data) < 8:
        raise ValueError('Truncated LogicLink header')
    magic, channel, length = struct.unpack_from('<HHI', data)
    if magic != 0xCC55 or channel not in (LOGIC_COMMAND_CHANNEL, LOGIC_VIDEO_CHANNEL):
        raise ValueError('Unsupported LogicLink header')
    if length != len(data)-8 or length > 65535:
        raise ValueError('LogicLink length mismatch')
    return channel, data[8:]


@dataclass(frozen=True)
class VideoProfile:
    receiver: Address
    logiclink: bool


# Android constructor defaults; the PC route is defined in pc_video.py.
PROFILES = {
    'zv900': VideoProfile(Address(0x1C, 1, 0x0900), True),
    'pigeon': VideoProfile(Address(0x0E, 1, 0x0701), False),
}


class VideoPacketizer:
    def __init__(self, profile, *, sequence=0, chunk_id=0):
        if profile not in PROFILES:
            raise ValueError('Choose an explicit native profile: zv900 or pigeon')
        check_uint(sequence, 32, 'sequence')
        check_uint(chunk_id, 32, 'chunk_id')
        self.profile = PROFILES[profile]
        self.sequence = sequence
        self.chunk_id = chunk_id

    def packetize(self, frame, *, timestamp_ms=None):
        """Return serialized V2 packets for one access unit, LogicLink-wrapped when the profile wraps."""
        packets = []
        for payload in video_fragments(frame, MAX_VIDEO_CHUNK, self.chunk_id, timestamp_ms):
            packet = V2Packet(*VIDEO, VIDEO_SENDER, self.profile.receiver, 3, self.sequence, payload).serialize()
            packets.append(wrap_logiclink(packet) if self.profile.logiclink else packet)
            self.sequence = (self.sequence + 1) & 0xFFFFFFFF
            self.chunk_id = (self.chunk_id + 1) & 0xFFFFFFFF
        return packets
