"""Incremental framing for the recovered mobile accessory byte stream."""
import struct
from .protocol import _bytes

CONTROL_CHANNELS = frozenset((0x5749, 0x7530))
VIDEO_CHANNEL = 0x574A


class LogicLinkStream:
    def __init__(self):
        self.buffer = bytearray()
        self.discarded = 0

    def feed(self, data):
        self.buffer.extend(_bytes(data))
        frames = []
        while len(self.buffer) >= 8:
            magic, channel, size = struct.unpack_from('<HHI', self.buffer)
            if magic != 0xCC55 or channel not in CONTROL_CHANNELS | {VIDEO_CHANNEL} or size > 65535:
                del self.buffer[0]
                self.discarded += 1
                continue
            if len(self.buffer) < 8 + size:
                break
            frames.append((channel, bytes(self.buffer[8:8+size])))
            del self.buffer[:8+size]
        return frames
