"""Emulate the native DUML V1 serializer in Unicorn."""
import struct
from research_common import load_binary_args, serializer_report, write_report

START = 0x049f5c74
END = START + 480

def pack_object(fields):
    # Native V1 object layout differs from the serialized wire layout.
    raw = bytearray(24)
    struct.pack_into('<BBBBBBB', raw, 0, fields['command_set'], fields['command_id'], fields['sender_type'], fields['sender_id'], fields['receiver_type'], fields['receiver_id'], fields['is_response'])
    struct.pack_into('<I', raw, 8, fields['ack'])
    struct.pack_into('<H', raw, 20, fields['sequence'])
    return raw

def main():
    args, binary = load_binary_args('v1-oracle.json')
    common = dict(command_set=0, command_id=0, sender_type=2, sender_id=0,
                  receiver_type=28, receiver_id=0, is_response=0, ack=2, sequence=0x1234)
    cases = [('heartbeat', common, bytes.fromhex('000020000000')),
             ('device_info', dict(common,command_id=255,receiver_id=1), b'\x00'),
             ('sim_mode', dict(common,command_set=11,command_id=26),bytes.fromhex('01010000')),
             ('response', dict(common,is_response=1,ack=0,sender_type=28,sender_id=0,receiver_type=2,receiver_id=0),b'\x00')]
    write_report(args, serializer_report(binary, START, END, 12, pack_object, cases))

if __name__ == '__main__':
    main()
