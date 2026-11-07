"""Packet formats recovered from the ARM Virtual Flight application.

No device access or session negotiation is implemented here. Native class names
identify profiles; they are not authenticated hardware model identifiers.
See .agents/PROTOCOL.md for evidence, addresses, and verification limits.
"""
from dataclasses import dataclass
import binascii
import struct
import time

MAX_VIDEO_CHUNK = 65404
V2_OVERHEAD = 29
VIDEO_HEADER_SIZE = 32
LOGIC_COMMAND_CHANNEL = 0x5749
LOGIC_VIDEO_CHANNEL = 0x574A


def _integer(value, bits, name):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f'{name} must be an unsigned {bits}-bit integer')


def _bytes(value):
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


@dataclass(frozen=True)
class Address:
    device_type: int
    device_id: int
    index: int

    def __post_init__(self):
        _integer(self.device_type, 8, 'device_type')
        _integer(self.device_id, 8, 'device_id')
        _integer(self.index, 16, 'index')

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
        _integer(self.command_set, 8, 'command_set')
        _integer(self.command_id, 8, 'command_id')
        _integer(self.ack, 3, 'ack')
        _integer(self.sequence, 32, 'sequence')
        payload = _bytes(self.payload)
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
        data = _bytes(data)
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
    """Add the app's eight-byte outer header; no USB endpoint is implied."""
    if channel not in (LOGIC_COMMAND_CHANNEL, LOGIC_VIDEO_CHANNEL):
        raise ValueError('Unsupported LogicLink channel')
    packet = _bytes(packet)
    if len(packet) > 65535:
        raise ValueError('Inner packet exceeds the recovered V2 limit')
    return struct.pack('<HHI', 0xCC55, channel, len(packet)) + packet


def unwrap_logiclink(data):
    data = _bytes(data)
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


# Names recovered from DeviceZV900Glass and DevicePigeonGlass constructors.
# The attached Goggles 2 has not been identified through the app's handshake.
PROFILES = {
    'zv900': VideoProfile(Address(0x1C, 1, 0x0900), True),
    'pigeon': VideoProfile(Address(0x0E, 1, 0x0701), False),
}


class VideoPacketizer:
    def __init__(self, profile, *, sequence=0, chunk_id=0):
        if profile not in PROFILES:
            raise ValueError('Choose an explicit native profile: zv900 or pigeon')
        _integer(sequence, 32, 'sequence')
        _integer(chunk_id, 32, 'chunk_id')
        self.profile = PROFILES[profile]
        self.sequence = sequence
        self.chunk_id = chunk_id

    def packetize(self, frame, *, timestamp_ms=None):
        """Encode one nonempty encoder output buffer, not a whole H.264 file.

        Caller supplies access-unit boundaries and valid encoded content. The
        app prepends saved codec configuration to keyframes. This method does
        not encode video or infer that configuration.

        The ARM app truncates epoch milliseconds to signed 32 bits, then widens
        to signed 64 bits. Reproduce that observed behavior deliberately. With
        no timestamp override, the clock is sampled for every fragment.
        """
        frame = _bytes(frame)
        if not frame:
            raise ValueError('Cannot packetize an empty video buffer')
        if timestamp_ms is not None and (type(timestamp_ms) is not int or not -(1 << 63) <= timestamp_ms < 1 << 63):
            raise ValueError('timestamp_ms must be a signed 64-bit integer')
        packets = []
        for offset in range(0, len(frame), MAX_VIDEO_CHUNK):
            chunk = frame[offset:offset+MAX_VIDEO_CHUNK]
            milliseconds = time.time_ns() // 1_000_000 if timestamp_ms is None else timestamp_ms
            timestamp = ((milliseconds + (1 << 31)) % (1 << 32)) - (1 << 31)
            header = struct.pack('<BBBBIqIIB7x', 0, len(frame) > MAX_VIDEO_CHUNK,
                                 offset+len(chunk) == len(frame), 0, self.chunk_id,
                                 timestamp, VIDEO_HEADER_SIZE, len(chunk), offset == 0)
            packet = V2Packet(0x0B, 0x53, VIDEO_SENDER, self.profile.receiver, 3,
                              self.sequence, header+chunk).serialize()
            packets.append(wrap_logiclink(packet) if self.profile.logiclink else packet)
            self.sequence = (self.sequence + 1) & 0xFFFFFFFF
            self.chunk_id = (self.chunk_id + 1) & 0xFFFFFFFF
        return packets
