"""Write PC V1 packets for one Annex-B access unit to a file."""
import argparse
import hashlib
from itertools import count
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from goggles_bridge.pc_video import PcVideoPacketizer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True,help='One complete access unit, with AUD removed')
    parser.add_argument('--output',type=Path,required=True,help='Binary output file path (must not already exist)')
    parser.add_argument('--timestamp-ms',type=int,default=1794000000123)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists')
    if not 0<args.frame.stat().st_size<=2*1024*1024:parser.error('Frame must be 1 byte to 2 MiB')
    frame=args.frame.read_bytes()
    if not frame.startswith((b'\0\0\1',b'\0\0\0\1')):parser.error('Expected Annex-B data')
    sequence=count()
    packets=PcVideoPacketizer().packetize(frame,sequence.__next__,timestamp_ms=args.timestamp_ms)
    wire=b''.join(packets)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:stream.write(wire)
    print(f'{len(packets)} packets; {len(wire)} bytes; SHA256 {hashlib.sha256(wire).hexdigest()}')


if __name__=='__main__':
    main()
