"""Record native SendVideo output at the emulated session boundary."""
import hashlib
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from research_common import EXIT, EXPECTED, load_binary_args, load_elf, write_report

START, END = 0x049f0128, 0x049f0128 + 1276

def run(binary, payload, milliseconds):
    uc = load_elf(binary)
    heap = 0x10100000
    packets = []
    u32 = lambda at: struct.unpack('<I', uc.mem_read(at,4))[0]
    counter = (struct.unpack_from('<I', binary, 0x49f05f8)[0] + 0x49f0330)&0xffffffff
    uc.mem_write(counter, struct.pack('<I', 0xfffffffe))

    def hook(machine, address, size, context):
        nonlocal heap
        if START <= address < END:
            return
        r0, r1, r2, r3 = [machine.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if address == 0x04f3c6dc:
            if r0 != 24:
                raise RuntimeError(f'Unexpected allocation {r0}')
            machine.reg_write(UC_ARM_REG_R0, heap)
            heap += 32
        elif address == 0x05397ad0:
            machine.mem_write(r0, struct.pack('<q', milliseconds*1000))
        elif address == 0x05395864:
            dividend = struct.unpack('<q',struct.pack('<II',r0,r1))[0]
            divisor = struct.unpack('<q',struct.pack('<II',r2,r3))[0]
            if divisor != 1000:
                raise RuntimeError(f'Unexpected divisor {divisor}')
            quotient = (abs(dividend)//abs(divisor)) * (-1 if (dividend<0)!=(divisor<0) else 1)
            machine.reg_write(UC_ARM_REG_R0, quotient&0xffffffff)
            machine.reg_write(UC_ARM_REG_R1, (quotient>>32)&0xffffffff)
        elif address == 0x05395944:
            if r2 > r3 or r2 > 65404:
                raise RuntimeError('Copy bounds')
            machine.mem_write(r0, bytes(machine.mem_read(r1,r2)))
        elif address == 0x049e3924:
            # Snapshot the object and its payload at the session boundary.
            mem = u32(r1+16)
            data, length = struct.unpack('<II',machine.mem_read(mem,8))
            raw = bytes(machine.mem_read(data,length))
            packets.append(dict(object_hex=bytes(machine.mem_read(r1,16)).hex(),
                                video_argument=r3, header_hex=raw[:32].hex(),
                                data_length=len(raw)-32, data_sha256=hashlib.sha256(raw[32:]).hexdigest()))
            # Retain a synthetic shared reference to avoid unrelated C++ destructors.
            owner = u32(r1+20)
            machine.mem_write(owner+4,struct.pack('<I',1))
        else:
            raise RuntimeError(f'Unexpected code execution {address:08x}')
        machine.reg_write(UC_ARM_REG_PC,machine.reg_read(UC_ARM_REG_LR))

    obj, callback, data, session = 0x10000100,0x10000200,0x10001000,0x10000300
    uc.mem_write(obj+4, struct.pack('<I',session))
    uc.mem_write(obj+12,struct.pack('<IIII',11,28,1,0x900))
    uc.mem_write(data,payload)
    for register,value in [(UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,data),(UC_ARM_REG_R2,len(payload)),(UC_ARM_REG_R3,callback),(UC_ARM_REG_SP,0x2000f000),(UC_ARM_REG_LR,EXIT)]:
        uc.reg_write(register,value)
    uc.hook_add(UC_HOOK_CODE,hook)
    uc.emu_start(START,EXIT,timeout=5_000_000,count=1_000_000)
    if uc.reg_read(UC_ARM_REG_PC)!=EXIT:
        raise RuntimeError('Instruction/time limit')
    return packets

if __name__ == '__main__':
    args,binary=load_binary_args('video-oracle.json')
    cases=[]
    for n in [1,65404,65405,130809]:
        raw=bytes(i%256 for i in range(n))
        cases.append(dict(length=n,milliseconds=1794000000123,initial_chunk_id=0xfffffffe,packets=run(binary,raw,1794000000123)))
    result=dict(binary_sha256=EXPECTED,function_elf_va=hex(START),emulator='Unicorn 2.1.4',
        hooks='allocator, controlled clock, signed division, bounded memcpy, intercepted SendV2Packet; retained synthetic shared reference',cases=cases)
    write_report(args,result)
