"""Write mobile V2 packets for one H.264 access unit to a file."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from goggles_bridge.protocol import VideoPacketizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='File containing one H.264 access unit')
    parser.add_argument('output', type=Path, help='Output file path (must not already exist)')
    parser.add_argument('--profile', choices=('zv900', 'pigeon'), required=True,
                        help='Android destination profile')
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
