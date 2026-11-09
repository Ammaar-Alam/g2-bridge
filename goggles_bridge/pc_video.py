"""Fragment H.264 video into DUML V1 packets for the Goggles 2 PC USB route.

See docs/PROTOCOL.md for the metadata layout and session requirements.
"""
from .control import GOGGLES, PC, V1_MAX_LENGTH, V1_OVERHEAD, V1Packet
from .duml import VIDEO, VIDEO_HEADER_SIZE, check_uint, video_fragments

MAX_PC_VIDEO_CHUNK = V1_MAX_LENGTH - V1_OVERHEAD - VIDEO_HEADER_SIZE


class PcVideoPacketizer:
    def __init__(self, *, chunk_id=0):
        check_uint(chunk_id, 32, 'chunk_id')
        self.chunk_id = chunk_id

    def packetize(self, frame, next_sequence, *, timestamp_ms=None):
        """Return serialized V1 packets numbered by the control session's next_sequence allocator."""
        payloads = video_fragments(frame, MAX_PC_VIDEO_CHUNK, self.chunk_id, timestamp_ms)
        self.chunk_id = (self.chunk_id+len(payloads)) & 0xFFFFFFFF
        return [V1Packet(*VIDEO, *PC, GOGGLES, 1, 0, 0, next_sequence(), payload).serialize() for payload in payloads]
