"""Emulate the native DUML V2 serializer in Unicorn."""
import struct
from research_common import load_binary_args, serializer_report, write_report

START = 0x049f6448
END = START + 664

def pack_object(fields):
    # Native V2 object layout differs from the serialized wire layout.
    raw = bytearray(24)
    struct.pack_into('<BBBBHBBHBxI', raw, 0, fields['command_set'], fields['command_id'],
                     fields['sender_type'], fields['sender_id'], fields['sender_index'],
                     fields['receiver_type'], fields['receiver_id'], fields['receiver_index'],
                     fields['ack'], fields['sequence'])
    return raw

def main():
    args, binary = load_binary_args('serializer-oracle.json')
    common = dict(command_set=11, command_id=83, sender_type=2, sender_id=0,
                  sender_index=257, receiver_type=28, receiver_id=1,
                  receiver_index=2304, ack=3, sequence=0x12345678)
    cases = [('empty', common, None),
             ('small', common, bytes.fromhex('000000016742001f')),
             ('different_fields', dict(command_set=1, command_id=254, sender_type=3,
                                      sender_id=4, sender_index=0x4321, receiver_type=5,
                                      receiver_id=6, receiver_index=0x8765, ack=2,
                                      sequence=0xfedcba98), bytes(range(32)))]
    write_report(args, serializer_report(binary, START, END, 16, pack_object, cases))

if __name__ == '__main__':
    main()
