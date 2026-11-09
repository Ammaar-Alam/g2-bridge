import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('probe_goggles', ROOT/'tools/research/probe_goggles.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def test_sysfs_layout_yields_first_configuration(self):
        config = bytes.fromhex(json.loads((ROOT/'tests/fixtures/usb-configuration.json').read_text())['configuration_hex'])
        device = bytes.fromhex('12010002ef020140a32c20000001010203') + b'\x01'
        self.assertEqual(probe.sysfs_configuration(device + config + config), config)
        for data in (device, b'\0' * 64, device + config[:-1]):
            with self.assertRaises(ValueError):
                probe.sysfs_configuration(data)

    def test_test_frame_is_pinned(self):
        import hashlib
        self.assertEqual(hashlib.sha256(probe.TEST_FRAME.read_bytes()).hexdigest(), probe.TEST_FRAME_SHA256)


    def test_route_scan_sends_one_request_at_a_time_and_skips_risky_modules(self):
        from dataclasses import replace
        rows, sent, sequence = [], [], iter(range(100))
        scan = probe.RouteScan(lambda event, **row: rows.append(row))
        now = 0.0
        while not scan.done:
            before = len(sent)
            scan.poll(now, sequence.__next__, sent.append)
            if len(sent) > before:
                request = sent[-1]
                # Modules 0, 1, 3 and 5 answer identity; only module 1 answers simulator mode
                if request.receiver_id in ((0, 1, 3, 5) if request.command_id == 0xff else (1,)):
                    scan.receive(replace(request, sender_type=28, sender_id=request.receiver_id,
                                         receiver_type=10, receiver_id=1, is_response=1, payload=b'\0'))
            now += probe.SCAN_WAIT
        commands = [(p.command_set, p.command_id, p.receiver_id) for p in sent]
        self.assertEqual(commands, [(0, 0xff, i) for i in range(8)] + [(11, 0x1a, 0), (11, 0x1a, 1)])
        self.assertEqual([len(r['replies']) for r in rows][-2:], [0, 1])
        self.assertEqual(rows[-1]['replies'][0]['sender'], '28/1')


if __name__ == '__main__':
    unittest.main()
