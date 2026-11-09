"""Load the pinned ARM binary into Unicorn, run its packet serializers, and write oracle reports."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP

EXPECTED = 'c75d099fa9b7a4962909171808857a51c4ef88a02f21e9ae40c1e05924c66df7'
EXIT = 0x30000000

def load_binary_args(filename):
    parser=argparse.ArgumentParser(description='Emulate ARM routines in Unicorn with instruction and time limits.')
    parser.add_argument('--binary',type=Path,required=True,help='Path to the pinned ARM32 libUE4.so extracted from the original APK')
    parser.add_argument('--output',type=Path,default=Path('work/research')/filename,help='Output file path (must not already exist)')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists; choose a new path')
    binary=args.binary.read_bytes()
    if hashlib.sha256(binary).hexdigest()!=EXPECTED:parser.error('Wrong native binary SHA-256')
    return args,binary

def load_elf(binary):
    """Map the loadable ELF segments, a heap at 0x10000000, a stack at 0x20000000, and the EXIT page."""
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
    return uc

def serialize(binary, start, end, native_object, payload_offset, payload):
    """Run a native packet serializer on a packed packet object and return its bytes and helper calls.

    The payload buffer pointer is written at payload_offset in the object.
    """
    uc = load_elf(binary)
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
        if start <= address < end:
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
    raw = bytearray(native_object)
    if payload is not None:
        struct.pack_into('<II', raw, payload_offset, mem, 0)
        uc.mem_write(mem, struct.pack('<II', data, len(payload)))
        if payload:
            uc.mem_write(data, payload)
    uc.mem_write(obj, bytes(raw))
    uc.reg_write(UC_ARM_REG_R0, out)
    uc.reg_write(UC_ARM_REG_R1, obj)
    uc.reg_write(UC_ARM_REG_SP, 0x2000f000)
    uc.reg_write(UC_ARM_REG_LR, EXIT)
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(start, EXIT, timeout=5_000_000, count=3_000_000)
    if uc.reg_read(UC_ARM_REG_PC) != EXIT:
        raise RuntimeError('Emulation instruction/time limit')
    result = struct.unpack('<I', uc.mem_read(out, 4))[0]
    pointer, length = struct.unpack('<II', uc.mem_read(result, 8))
    if length > 65535:
        raise RuntimeError('Output length limit')
    return bytes(uc.mem_read(pointer, length)), calls

def serializer_report(binary, start, end, payload_offset, pack_object, cases):
    """Serialize each (name, fields, payload) case with pack_object(fields) as the native object."""
    results = []
    for name, fields, payload in cases:
        packet, calls = serialize(binary, start, end, pack_object(fields), payload_offset, payload)
        results.append(dict(name=name, fields=fields, payload_hex=(payload or b'').hex(),
                            packet_hex=packet.hex(), hooks=calls))
    return dict(binary_sha256=EXPECTED, function_elf_va=hex(start), emulator='Unicorn 2.1.4',
                limit='memory-only; 3M instructions / 5 seconds per case', cases=results)

def write_report(args,result):
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(f'Saved {len(result["cases"])} native oracle cases to {args.output}')
