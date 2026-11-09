"""Fragment H.264 video into DUML V1 packets for the goggles PC USB route.

See docs/PROTOCOL.md for the metadata layout and session requirements. The
destination defaults to the Goggles 2 glasses module, 28/1; a model profile
can direct video elsewhere, such as the FPV Goggles V2's HD-link module 14/1.
"""
import struct
import time
from .control import V1Packet
from .protocol import _bytes, _integer

MAX_PC_VIDEO_CHUNK = 1023 - 13 - 32
DEFAULT_RECEIVER = (28, 1)


class PcVideoPacketizer:
    def __init__(self, *, chunk_id=0, receiver=DEFAULT_RECEIVER):
        _integer(chunk_id, 32, 'chunk_id')
        receiver_type, receiver_id = receiver
        _integer(receiver_type, 5, 'receiver_type')
        _integer(receiver_id, 3, 'receiver_id')
        self.chunk_id = chunk_id
        self.receiver = (receiver_type, receiver_id)

    def packetize(self, frame, next_sequence, *, timestamp_ms=None):
        """Yield V1 packets using the control session's next_sequence allocator."""
        frame = _bytes(frame)
        if not frame:
            raise ValueError('Empty H.264 access unit')
        if timestamp_ms is not None:
            _integer(timestamp_ms, 63, 'timestamp_ms')
        for offset in range(0, len(frame), MAX_PC_VIDEO_CHUNK):
            chunk = frame[offset:offset+MAX_PC_VIDEO_CHUNK]
            milliseconds = time.time_ns()//1_000_000 if timestamp_ms is None else timestamp_ms
            timestamp = ((milliseconds+(1<<31))%(1<<32))-(1<<31)
            metadata = struct.pack('<BBBBIqIIB7x', 0, len(frame)>MAX_PC_VIDEO_CHUNK,
                                   offset+len(chunk)==len(frame), 0, self.chunk_id,
                                   timestamp, 32, len(chunk), offset==0)
            packet = V1Packet(11, 0x53, 10, 1, self.receiver[0], self.receiver[1], 0, 0,
                              next_sequence(), metadata+chunk)
            self.chunk_id = (self.chunk_id+1)&0xffffffff
            yield packet
