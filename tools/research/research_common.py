"""Parse research CLI arguments, verify the binary hash, and write reports."""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = 'c75d099fa9b7a4962909171808857a51c4ef88a02f21e9ae40c1e05924c66df7'

def load_binary_args(filename):
    parser=argparse.ArgumentParser(description='Emulate ARM routines in Unicorn with instruction and time limits.')
    parser.add_argument('--binary',type=Path,required=True,help='Path to the pinned ARM32 libUE4.so extracted from the original APK')
    parser.add_argument('--output',type=Path,default=Path('work/research')/filename,help='Output file path (must not already exist)')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists; choose a new path')
    binary=args.binary.read_bytes()
    if hashlib.sha256(binary).hexdigest()!=EXPECTED:parser.error('Wrong native binary SHA-256')
    return args,binary

def write_report(args,result):
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(f'Saved {len(result["cases"])} native oracle cases to {args.output}')
