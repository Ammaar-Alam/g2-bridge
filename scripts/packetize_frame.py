"""Write offline packets for ONE encoded video access unit. Does not access USB."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goggles_bridge.protocol import VideoPacketizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='One H.264 encoder output buffer; not a multi-frame stream')
    parser.add_argument('output', type=Path, help='New output file; refuses overwrite')
    parser.add_argument('--profile', choices=('zv900', 'pigeon'), required=True,
                        help='Native class profile; hardware mapping remains unverified')
    parser.add_argument('--sequence', type=int, default=0)
    parser.add_argument('--chunk-id', type=int, default=0)
    parser.add_argument('--timestamp-ms', type=int)
    args = parser.parse_args()
    try:
        packetizer = VideoPacketizer(args.profile, sequence=args.sequence, chunk_id=args.chunk_id)
        packets = packetizer.packetize(args.input.read_bytes(), timestamp_ms=args.timestamp_ms)
        with args.output.open('xb') as stream:
            for packet in packets:
                stream.write(packet)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(f'Wrote {len(packets)} offline packet(s), {sum(map(len, packets))} bytes; '
          f'next sequence={packetizer.sequence}, chunk_id={packetizer.chunk_id}. No device traffic sent.')


if __name__ == '__main__':
    main()
