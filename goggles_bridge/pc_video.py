"""Stock Goggles 2 PC video, visually verified on firmware 01.11.00.00.

The recovered mobile payload is fragmented to fit raw DUML V1. The original
mobile V2 envelope did not display video on the PC interface. See LIVE.md.
"""
import struct
import time
from .control import V1Packet
from .protocol import _bytes, _integer

MAX_PC_VIDEO_CHUNK = 1023 - 13 - 32


class PcVideoPacketizer:
    def __init__(self, *, chunk_id=0):
        _integer(chunk_id, 32, 'chunk_id')
        self.chunk_id = chunk_id

    def packetize(self, frame, next_sequence, *, timestamp_ms=None):
        """Yield V1 packets; next_sequence is shared with the control session."""
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
            packet = V1Packet(11, 0x53, 10, 1, 28, 1, 0, 0,
                              next_sequence(), metadata+chunk)
            self.chunk_id = (self.chunk_id+1)&0xffffffff
            yield packet
