"""Minimal single-stream AVI with arbitrary encoded packet payloads."""
import struct


def chunk(tag, payload):
    return tag+struct.pack('<I', len(payload))+payload+b'\0'*(len(payload)&1)


def header():
    avih = bytearray(56)
    struct.pack_into('<I', avih, 24, 1)
    strh = b'vidsH264'+bytes(48)
    strf = bytearray(40)
    struct.pack_into('<I', strf, 0, 40)
    strf[16:20] = b'H264'
    hdrl = chunk(b'avih', avih)+chunk(b'LIST', b'strl'+chunk(b'strh', strh)+chunk(b'strf', strf))
    return (b'RIFF\xff\xff\xff\xffAVI '+chunk(b'LIST', b'hdrl'+hdrl)
            +b'LIST\xff\xff\xff\xffmovi')


def stream(packets):
    return header()+b''.join(chunk(b'00dc', packet) for packet in packets)
