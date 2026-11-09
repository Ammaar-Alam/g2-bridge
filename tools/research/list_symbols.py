"""List ELF function symbols of a native library and write a Ghidra target list.

    python tools/research/list_symbols.py --binary work/native/libUE4.so --match Pigeon Glass Sim \
        --output work/research/pigeon-targets.tsv

The output has the columns FocusedNative.java reads: ELF virtual address (hex),
size, Thumb state (1 when the symbol's address has bit 0 set), and the mangled
name. Addresses are original ELF VAs; the Ghidra script adds the import base.
"""
import argparse
from pathlib import Path
import sys

try:
    from elftools.elf.elffile import ELFFile
except ImportError:
    sys.exit('pyelftools is required: python -m pip install pyelftools')


def function_symbols(path):
    with Path(path).open('rb') as handle:
        elf = ELFFile(handle)
        for section_name in ('.symtab', '.dynsym'):
            section = elf.get_section_by_name(section_name)
            if section is None:
                continue
            for symbol in section.iter_symbols():
                if symbol['st_info']['type'] != 'STT_FUNC' or symbol['st_size'] == 0:
                    continue
                value = symbol['st_value']
                yield value & ~1, symbol['st_size'], value & 1, symbol.name


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--match', nargs='*', default=[], help='Keep symbols whose name contains any of these')
    parser.add_argument('--output', type=Path, help='Target TSV to write; prints to stdout otherwise')
    parser.add_argument('--demangle', action='store_true', help='Show demangled names (needs c++filt on PATH)')
    args = parser.parse_args()
    seen = {}
    for address, size, thumb, name in function_symbols(args.binary):
        if args.match and not any(m in name for m in args.match):
            continue
        seen[(address, name)] = (address, size, thumb, name)
    rows = sorted(seen.values())
    lines = [f'{address:08x}\t{size}\t{thumb}\t{name}' for address, size, thumb, name in rows]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'{len(lines)} symbols -> {args.output}')
    else:
        print('\n'.join(lines))


if __name__ == '__main__':
    main()
