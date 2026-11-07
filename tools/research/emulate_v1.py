"""Emulate the native DUML V1 serializer in Unicorn."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *
from research_common import EXPECTED, load_binary_args, write_report

START = 0x049f5c74
END = START + 480
EXIT = 0x30000000

def serialize(binary, fields, payload):
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    phoff = struct.unpack_from('<I', binary, 28)[0]
    size, count = struct.unpack_from('<HH', binary, 42)
    segments = [struct.unpack_from('<8I', binary, phoff + i * size) for i in range(count)]
    last = max(p[2] + p[5] for p in segments if p[0] == 1)
    uc.mem_map(0, (last + 4095) & ~4095)
    for p in segments:
        if p[0] == 1:
            uc.mem_write(p[2], binary[p[1]:p[1] + p[4]])
    uc.mem_map(0x10000000, 0x1000000)
    uc.mem_map(0x20000000, 0x10000)
    uc.mem_map(EXIT, 0x1000)
    heap = 0x10100000
    calls = {}

    def alloc(size):
        nonlocal heap
        if not 0 < size <= 0x100000:
            raise RuntimeError(f'Unexpected allocation {size}')
        result = heap
        heap += (size + 15) & ~15
        if heap >= 0x11000000:
            raise RuntimeError('Heap limit')
        return result

    def hook(machine, address, size, context):
        if START <= address < END:
            return
        r0 = machine.reg_read(UC_ARM_REG_R0)
        r1 = machine.reg_read(UC_ARM_REG_R1)
        r2 = machine.reg_read(UC_ARM_REG_R2)
        calls[hex(address)] = calls.get(hex(address), 0) + 1
        if address in (0x04f3c6dc, 0x05395fbc):
            machine.reg_write(UC_ARM_REG_R0, alloc(r0))
        elif address == 0x05395fcc:
            if r1 > 0x100000:
                raise RuntimeError('Zero-fill limit')
            machine.mem_write(r0, bytes(r1))
        elif address == 0x05395814:
            if r2 > 0x100000:
                raise RuntimeError('Copy limit')
            if r2:
                machine.mem_write(r0, bytes(machine.mem_read(r1, r2)))
        else:
            raise RuntimeError(f'Unexpected code execution {address:08x}')
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    out, obj, mem, data = 0x10000000, 0x10000100, 0x10000200, 0x10001000
    # Native V1 object layout differs from the serialized wire layout.
    raw = bytearray(24)
    struct.pack_into('<BBBBBBB', raw, 0, fields['command_set'], fields['command_id'], fields['sender_type'], fields['sender_id'], fields['receiver_type'], fields['receiver_id'], fields['is_response'])
    struct.pack_into('<I', raw, 8, fields['ack'])
    struct.pack_into('<H', raw, 20, fields['sequence'])
    if payload is not None:
        struct.pack_into('<II', raw, 12, mem, 0)
        uc.mem_write(mem, struct.pack('<II', data, len(payload)))
        if payload:
            uc.mem_write(data, payload)
    uc.mem_write(obj, bytes(raw))
    uc.reg_write(UC_ARM_REG_R0, out)
    uc.reg_write(UC_ARM_REG_R1, obj)
    uc.reg_write(UC_ARM_REG_SP, 0x2000f000)
    uc.reg_write(UC_ARM_REG_LR, EXIT)
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(START, EXIT, timeout=5_000_000, count=3_000_000)
    if uc.reg_read(UC_ARM_REG_PC) != EXIT:
        raise RuntimeError('Emulation instruction/time limit')
    result = struct.unpack('<I', uc.mem_read(out, 4))[0]
    pointer, length = struct.unpack('<II', uc.mem_read(result, 8))
    if length > 65535:
        raise RuntimeError('Output length limit')
    return bytes(uc.mem_read(pointer, length)), calls

def main():
    args, binary = load_binary_args('v1-oracle.json')
    digest = hashlib.sha256(binary).hexdigest()
    if digest != EXPECTED:
        raise RuntimeError('Wrong binary hash')
    common = dict(command_set=0, command_id=0, sender_type=2, sender_id=0,
                  receiver_type=28, receiver_id=0, is_response=0, ack=2, sequence=0x1234)
    cases = [('heartbeat', common, bytes.fromhex('000020000000')),
             ('device_info', dict(common,command_id=255,receiver_id=1), b'\x00'),
             ('sim_mode', dict(common,command_set=11,command_id=26),bytes.fromhex('01010000')),
             ('response', dict(common,is_response=1,ack=0,sender_type=28,sender_id=0,receiver_type=2,receiver_id=0),b'\x00')]
    results = []
    for name, fields, payload in cases:
        packet, calls = serialize(binary, fields, payload)
        results.append(dict(name=name, fields=fields, payload_hex=(payload or b'').hex(),
                            packet_hex=packet.hex(), hooks=calls))
    output = dict(binary_sha256=digest, function_elf_va=hex(START), emulator='Unicorn 2.1.4',
                  limit='memory-only; 3M instructions / 5 seconds per case', cases=results)
    write_report(args, output)

if __name__ == '__main__':
    main()
