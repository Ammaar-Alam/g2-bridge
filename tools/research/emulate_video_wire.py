"""Check native video packet bytes at the intercepted AsyncIO call."""
import hashlib
from pathlib import Path
import struct
import sys
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from research_common import EXIT, EXPECTED, load_binary_args, load_elf, write_report

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from goggles_bridge.protocol import VideoPacketizer, unwrap_logiclink
IO = EXIT + 0x100
RANGES = ((0x49f0128,1276),(0x49e3924,648),(0x49f6448,664))

def run(binary, data, logiclink):
    uc = load_elf(binary)
    heap = 0x10100000
    owners = []
    output = []
    hooks = {}
    milliseconds = 1794000000123
    def u32(a): return struct.unpack('<I',uc.mem_read(a,4))[0]
    def w32(a,v): uc.mem_write(a,struct.pack('<I',v))
    def alloc(n):
        nonlocal heap
        if not 0 < n <= 1048576: raise RuntimeError('Unexpected allocation')
        at=heap;heap+=(n+15)&~15
        if heap>=0x11000000:raise RuntimeError('Heap bound')
        if n==24:owners.append(at)
        return at
    counter = (struct.unpack_from('<I',binary,0x49f05f8)[0]+0x49f0330)&0xffffffff
    w32(counter,0)
    got=(struct.unpack_from('<I',binary,0x49e3ba8)[0]+0x49e3968)&0xffffffff
    w32(u32(got),0)

    def hook(machine,address,size,context):
        if any(a<=address<a+n for a,n in RANGES):return
        hooks[hex(address)]=hooks.get(hex(address),0)+1
        r0,r1,r2,r3=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if address in (0x4f3c6dc,0x5395fbc):
            uc.reg_write(UC_ARM_REG_R0,alloc(r0))
        elif address==0x5395fcc:
            if r1>1048576:raise RuntimeError('Zero bound')
            uc.mem_write(r0,bytes(r1))
        elif address in (0x5395814,0x5395944):
            if r2>1048576 or (address==0x5395944 and r2>r3):raise RuntimeError('Copy bound')
            if r2:uc.mem_write(r0,bytes(uc.mem_read(r1,r2)))
        elif address==0x5397ad0:
            uc.mem_write(r0,struct.pack('<q',milliseconds*1000))
        elif address==0x5395864:
            value=struct.unpack('<q',struct.pack('<II',r0,r1))[0]
            if (r2,r3)!=(1000,0):raise RuntimeError('Division argument')
            value=value//1000
            uc.reg_write(UC_ARM_REG_R0,value&0xffffffff)
            uc.reg_write(UC_ARM_REG_R1,(value>>32)&0xffffffff)
        elif address==0x49e959c:
            owner=alloc(24);payload=alloc(r1)
            uc.mem_write(owner,struct.pack('<6I',0,1000,1000,payload,r1,0))
            uc.mem_write(r0,struct.pack('<II',owner+12,owner))
        elif address==0x49e94bc:
            if r3+r2>u32(r0+4):raise RuntimeError('MemData copy bound')
            if r2:uc.mem_write(u32(r0)+r3,bytes(uc.mem_read(r1,r2)))
        elif address==0x4f3c6e4:
            pass
        elif address==IO:
            if not 1<=r2<=65543:raise RuntimeError('Output bound')
            output.append(bytes(uc.mem_read(r1,r2)))
            for owner in owners:w32(owner+4,1000)
            uc.reg_write(UC_ARM_REG_R0,r2)
        else:
            raise RuntimeError(f'Unexpected execution {address:08x}')
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))

    obj,callback,payload,session,asyncio,vtable=0x10000100,0x10000200,0x10001000,0x10000300,0x10000400,0x10000500
    w32(obj+4,session)
    uc.mem_write(obj+12,struct.pack('<IIII',11,28,1,0x900))
    w32(session+12,asyncio)
    uc.mem_write(session+0x34,bytes((int(logiclink),)))
    w32(asyncio,vtable);w32(vtable+0x20,IO)
    uc.mem_write(payload,data)
    for reg,value in [(UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,payload),(UC_ARM_REG_R2,len(data)),(UC_ARM_REG_R3,callback),(UC_ARM_REG_SP,0x2000f000),(UC_ARM_REG_LR,EXIT)]:uc.reg_write(reg,value)
    uc.hook_add(UC_HOOK_CODE,hook)
    uc.emu_start(0x49f0128,EXIT,timeout=20_000_000,count=20_000_000)
    if uc.reg_read(UC_ARM_REG_PC)!=EXIT:raise RuntimeError('Execution budget exceeded')
    expected=VideoPacketizer('zv900').packetize(data,timestamp_ms=milliseconds)
    if not logiclink:expected=[unwrap_logiclink(x)[1] for x in expected]
    if output!=expected:raise RuntimeError('Native complete-wire pipeline differs from Python')
    return dict(length=len(data),logiclink=logiclink,packets=len(output),
                sha256=hashlib.sha256(b''.join(output)).hexdigest(),hooks=hooks)

if __name__ == '__main__':
    args,binary=load_binary_args('video-wire-oracle.json')
    cases=[]
    for data in (bytes(range(200)),bytes(i%256 for i in range(130809))):
        for wrapped in (False,True):
            cases.append(run(binary,data,wrapped))
    write_report(args,dict(binary_sha256=EXPECTED,cases=cases))
