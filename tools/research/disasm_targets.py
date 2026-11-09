"""Disassemble target functions of an ARM32 library with call targets named from its symbols.

    python tools/research/disasm_targets.py --binary work/native/libUE4.so \
        --targets work/research/glass-targets.tsv --output work/research/glass-disasm.txt

A fallback for reading the send path when a decompiler is unavailable: each
`bl`/`blx` is annotated with the symbol at its destination, PC-relative loads
are resolved to their constants, and string literals are shown inline.
"""
import argparse
from pathlib import Path
import struct
import sys

try:
    from elftools.elf.elffile import ELFFile
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
except ImportError:
    sys.exit('Install pyelftools and capstone: python -m pip install pyelftools capstone')


class Library:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        self.elf = ELFFile(Path(path).open('rb'))
        self.segments = [(s['p_vaddr'], s['p_filesz'], s['p_offset']) for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.symbols = {}
        for name in ('.symtab', '.dynsym'):
            section = self.elf.get_section_by_name(name)
            if section is None:
                continue
            for symbol in section.iter_symbols():
                if symbol['st_info']['type'] in ('STT_FUNC', 'STT_OBJECT') and symbol.name:
                    self.symbols.setdefault(symbol['st_value'] & ~1, symbol.name)

    def offset(self, va):
        for vaddr, size, offset in self.segments:
            if vaddr <= va < vaddr + size:
                return va - vaddr + offset
        return None

    def read(self, va, size):
        offset = self.offset(va)
        return self.data[offset:offset + size] if offset is not None else b''

    def word(self, va):
        raw = self.read(va, 4)
        return struct.unpack('<I', raw)[0] if len(raw) == 4 else None

    def string_at(self, va, limit=80):
        raw = self.read(va, limit)
        end = raw.find(b'\0')
        text = raw[:end if end >= 0 else limit]
        if len(text) >= 3 and all(32 <= b < 127 for b in text):
            return text.decode()
        return None

    def name(self, va):
        return self.symbols.get(va & ~1)


def disassemble(lib, va, size, thumb, out):
    code = lib.read(va, size)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if thumb else CS_MODE_ARM)
    md.detail = True
    for insn in md.disasm(code, va):
        note = ''
        if insn.mnemonic in ('bl', 'blx', 'b', 'bx') and insn.op_str.startswith('#'):
            target = int(insn.op_str[1:], 16)
            name = lib.name(target)
            note = f'  ; {name}' if name else ''
        elif insn.mnemonic == 'ldr' and '[pc' in insn.op_str:
            # ldr rX, [pc, #imm] loads a literal; ARM PC is insn+8, Thumb insn+4 aligned
            try:
                imm = int(insn.op_str.split('#')[1].rstrip(']'), 0)
            except (IndexError, ValueError):
                imm = 0
            base = (insn.address + 8) if not thumb else ((insn.address + 4) & ~3)
            literal = lib.word(base + imm)
            if literal is not None:
                desc = f'0x{literal:x}'
                text = lib.string_at(literal)
                name = lib.name(literal)
                if text:
                    desc += f' "{text}"'
                elif name:
                    desc += f' {name}'
                note = f'  ; ={desc}'
        out.write(f'{insn.address:08x}  {insn.mnemonic:7} {insn.op_str}{note}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--targets', type=Path, required=True, help='TSV: hex VA, size, thumb, name')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', nargs='*', default=[], help='Only targets whose name contains one of these')
    args = parser.parse_args()
    lib = Library(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as out:
        for line in args.targets.read_text().splitlines():
            if not line.strip():
                continue
            va, size, thumb, name = line.split('\t', 3)
            if args.only and not any(k in name for k in args.only):
                continue
            out.write(f'\n===== {name} @ {va} size {size} {"thumb" if thumb == "1" else "arm"} =====\n')
            disassemble(lib, int(va, 16), int(size), thumb == '1', out)
    print(f'wrote {args.output}')


if __name__ == '__main__':
    main()
