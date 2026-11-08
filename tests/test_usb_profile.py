import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from goggles_bridge.usb_transport import _select_control_device, DeviceNotFoundError, LinkSpeedError


class Interface:
    def __init__(self, observed):
        self.bInterfaceNumber = observed['number']
        self.bAlternateSetting = observed['alternate']
        self.bInterfaceClass = observed['usb_class']
        self.bInterfaceSubClass = observed['subclass']
        self.bInterfaceProtocol = observed['protocol']
        self.endpoints = [SimpleNamespace(bEndpointAddress=int(e['address'], 16),
            bmAttributes=e['transfer_type'], wMaxPacketSize=e['max_packet_size']) for e in observed['endpoints']]

    def __iter__(self):
        return iter(self.endpoints)


class UsbProfileTests(unittest.TestCase):
    def device(self, key):
        fixture = json.loads((Path(__file__).parent/'fixtures/usb-link-profiles.json').read_text())
        return [[Interface(row) for row in fixture[key]['interfaces']]]

    def test_observed_high_speed_is_selected(self):
        device = self.device('high_speed')
        self.assertIs(_select_control_device([device]), device)

    def test_observed_full_speed_is_explained_and_never_claimed(self):
        with self.assertRaisesRegex(LinkSpeedError, '12 Mbps'):
            _select_control_device([self.device('full_speed')])

    def test_superspeed_is_claimed_only_on_request(self):
        device = self.device('high_speed')
        for interface in device[0]:
            for endpoint in interface:
                endpoint.wMaxPacketSize = 1024
        with self.assertRaisesRegex(LinkSpeedError, 'SuperSpeed'):
            _select_control_device([device])
        self.assertIs(_select_control_device([device], allow_superspeed=True), device)

    def test_two_devices_are_ambiguous_even_if_one_is_slow(self):
        with self.assertRaisesRegex(RuntimeError, 'found 2'):
            _select_control_device([self.device('high_speed'), self.device('full_speed')])

    def test_other_interface_and_absence_are_not_selected(self):
        device = self.device('high_speed')
        device[0] = [i for i in device[0] if i.bInterfaceNumber != 4]
        for devices in ([], [device]):
            with self.assertRaises(DeviceNotFoundError):
                _select_control_device(devices)
