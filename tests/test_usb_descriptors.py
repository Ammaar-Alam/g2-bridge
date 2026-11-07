import importlib.util
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('usb_descriptors', ROOT/'scripts/read_usb_descriptors.py')
usb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb)


class DescriptorTests(unittest.TestCase):
    def test_observed_configuration(self):
        fixture = json.loads((ROOT/'tests/fixtures/usb-configuration.json').read_text())
        config = usb.parse_configuration(bytes.fromhex(fixture['configuration_hex']))
        self.assertEqual(config['interface_count'],8)
        self.assertEqual(len(config['interfaces']),8)
        vendor = config['interfaces'][3:]
        for i, interface in enumerate(vendor,3):
            self.assertEqual((interface['number'],interface['usb_class'],interface['subclass'],interface['protocol']),(i,255,67,1))
            self.assertEqual({e['address'] for e in interface['endpoints']},{f'0x{i:02x}',f'0x{i+129:02x}'})
            self.assertTrue(all(e['max_packet_size']==512 for e in interface['endpoints']))

    def test_malformed_descriptors(self):
        # One interface with one bulk endpoint.
        good = bytes.fromhex('0902190001010080320904000001ff43010007050302000200')
        self.assertEqual(len(usb.parse_configuration(good)['interfaces']),1)
        cases = [good[:-1],bytes(9),good[:9]+b'\x00'+good[10:]]
        no_interface = bytearray(good[:9]+good[18:])
        struct.pack_into('<H',no_interface,2,len(no_interface))
        cases.append(no_interface)
        bad_count = bytearray(good)
        bad_count[13] = 2
        cases.append(bad_count)
        for data in cases:
            with self.subTest(data=bytes(data).hex()),self.assertRaises(ValueError):
                usb.parse_configuration(data)


if __name__ == '__main__':
    unittest.main()
