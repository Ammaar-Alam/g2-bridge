"""Access units from an encoder explicitly configured to emit H.264 AUDs.

This is not a general H.264 picture parser. Delimiters are used for splitting
and removed from the transmitted access unit. SPS/PPS and all other NALs are
preserved exactly, including codec configuration before keyframes.
"""
import re
from .protocol import _bytes

_AUD = re.compile(rb'\x00\x00(?:\x00)?\x01\x09')
_START = re.compile(rb'\x00\x00(?:\x00)?\x01')


class AccessUnitStream:
    def __init__(self, max_frame_bytes=2 * 1024 * 1024):
        if type(max_frame_bytes) is not int or max_frame_bytes < 16:
            raise ValueError('Invalid frame limit')
        self.limit = max_frame_bytes
        self.buffer = bytearray()

    def _without_aud(self, data):
        if not _AUD.match(data):
            raise ValueError('Encoder output must begin each access unit with an AUD')
        match = _START.search(data, _AUD.match(data).end())
        if match is None:
            raise ValueError('Empty H.264 access unit')
        return bytes(data[match.start():])

    def feed(self, data):
        self.buffer.extend(_bytes(data))
        boundaries = [match.start() for match in _AUD.finditer(self.buffer)]
        frames = []
        if boundaries and boundaries[0] != 0:
            raise ValueError('Unexpected bytes before initial AUD')
        for start, end in zip(boundaries, boundaries[1:]):
            if end - start > self.limit:
                raise ValueError('H.264 access unit exceeds configured bound')
            frames.append(self._without_aud(self.buffer[start:end]))
        if len(boundaries) > 1:
            del self.buffer[:boundaries[-1]]
        if len(self.buffer) > self.limit:
            raise ValueError('H.264 access unit exceeds configured bound')
        return frames

    def finish(self):
        if not self.buffer:
            return []
        result = self._without_aud(self.buffer)
        self.buffer.clear()
        return [result]
