"""Model profiles, routes and picture sizes, including the untested FPV Goggles V2 path."""
from dataclasses import replace
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

from goggles_bridge import models
from goggles_bridge.control import V1Packet, V1Stream
from goggles_bridge.engine import BridgeSettings, encoder_command
from goggles_bridge.firmware import ManifestReader
from goggles_bridge.pc_video import PcVideoPacketizer
from goggles_bridge.session import ControlSession, SessionError, MODELS, EXPERIMENTAL_MODELS
from goggles_bridge.usb_transport import DeviceNotFoundError, select_control_link
from test_engine import EngineTests, FakeEncoder, FakeUsb


def answer(request, payload=b'\0'):
    return replace(request, sender_type=request.receiver_type, sender_id=request.receiver_id,
                   receiver_type=request.sender_type, receiver_id=request.sender_id,
                   is_response=1, ack=2, payload=payload)


class ModelTableTests(unittest.TestCase):
    def test_identity_codes(self):
        self.assertIs(models.match_identity('E3T ZV900 AC Aug 11 2026|07:21:27'), models.GOGGLES_2)
        self.assertIs(models.match_identity('e3t zv901 ac'), models.GOGGLES_INTEGRA)
        self.assertIs(models.match_identity('E3T ZV902 AC'), models.GOGGLES_3)
        self.assertIsNone(models.match_identity('GL170 something'))
        self.assertEqual(MODELS, {'ZV900': 'DJI Goggles 2', 'ZV901': 'DJI Goggles Integra'})
        self.assertEqual(EXPERIMENTAL_MODELS, {'ZV902': 'DJI Goggles 3'})

    def test_v2_profile_follows_the_app(self):
        v2 = models.FPV_GOGGLES_V2
        self.assertEqual((v2.width, v2.height, v2.video, v2.control, v2.identity), (1440, 810, (14, 1), (28, 0), (28, 1)))
        self.assertFalse(v2.tested)
        self.assertEqual(v2.size, '1440x810')
        self.assertIn(0x001f, models.PRODUCT_IDS)


class SessionRouteTests(unittest.TestCase):
    def test_unknown_identity_needs_assume_model(self):
        session = ControlSession()
        request, = session.poll(0)
        info, = session.receive(answer(request), .01)
        with self.assertRaisesRegex(SessionError, 'Unsupported goggles'):
            session.receive(answer(info, b'\0GL170 AC Jan 01 2024'), .02)

    def test_assumed_model_sets_profile_and_keeps_routes(self):
        session = ControlSession(assume_model='DJI FPV Goggles V2')
        hb, = session.poll(0)
        self.assertEqual((hb.receiver_type, hb.receiver_id), (28, 0))
        info, = session.receive(answer(hb), .01)
        self.assertEqual((info.receiver_type, info.receiver_id), (28, 1))
        mode, = session.receive(answer(info, b'\0GL170 AC'), .02)
        self.assertEqual((mode.command_set, mode.command_id, mode.receiver_type, mode.receiver_id), (11, 26, 28, 0))
        self.assertEqual(session.model, 'DJI FPV Goggles V2')
        self.assertIs(session.profile, models.FPV_GOGGLES_V2)
        # A known identity still wins over the assumption
        session = ControlSession(assume_model='DJI FPV Goggles V2')
        hb, = session.poll(0)
        info, = session.receive(answer(hb), .01)
        session.receive(answer(info, b'\0E3T ZV900 AC'), .02)
        self.assertIs(session.profile, models.GOGGLES_2)

    def test_control_type_moves_every_control_request(self):
        session = ControlSession(control_type=14, assume_model='DJI FPV Goggles V1')
        hb, = session.poll(0)
        self.assertEqual((hb.receiver_type, hb.receiver_id), (14, 0))
        info, = session.receive(answer(hb), .01)
        self.assertEqual((info.receiver_type, info.receiver_id), (14, 1))
        mode, = session.receive(answer(info, b'\0unknown'), .02)
        self.assertEqual((mode.receiver_type, mode.receiver_id), (14, 0))
        session.receive(answer(mode), .03)
        self.assertEqual(session.state, 'ready')
        # Replies from the old route are ignored
        session = ControlSession(control_type=14)
        hb, = session.poll(0)
        self.assertEqual(session.receive(replace(answer(hb), sender_type=28), .01), [])
        self.assertEqual(session.state, 'heartbeat')

    def test_invalid_options(self):
        with self.assertRaisesRegex(ValueError, 'Unknown model'):
            ControlSession(assume_model='DJI Goggles 9')
        with self.assertRaises(ValueError):
            ControlSession(control_type=32)
        with self.assertRaisesRegex(ValueError, 'Unknown model'):
            BridgeSettings(Path('d.dll'), Path('f.exe'), assume_model='nope')
        with self.assertRaises(ValueError):
            BridgeSettings(Path('d.dll'), Path('f.exe'), control_type=-1)


class VideoRouteTests(unittest.TestCase):
    def test_pc_packetizer_receiver(self):
        packet, = PcVideoPacketizer(receiver=(14, 1)).packetize(b'abc', lambda: 1, timestamp_ms=0)
        self.assertEqual((packet.receiver_type, packet.receiver_id, packet.sender_type, packet.sender_id), (14, 1, 10, 1))
        default, = PcVideoPacketizer().packetize(b'abc', lambda: 1, timestamp_ms=0)
        self.assertEqual((default.receiver_type, default.receiver_id), (28, 1))
        self.assertEqual(V1Packet.parse(packet.serialize()), packet)
        with self.assertRaises(ValueError):
            PcVideoPacketizer(receiver=(32, 1))

    def test_manifest_request_receiver(self):
        reader = ManifestReader(receiver=(14, 5))
        request, = reader.poll(0, lambda: 9)
        self.assertEqual((request.receiver_type, request.receiver_id, request.command_id), (14, 5, 0x4f))

    def test_encoder_command_takes_the_model_size(self):
        settings = BridgeSettings(Path('d.dll'), Path('ffmpeg.exe'))
        gfx = encoder_command(settings, (1440, 810))
        self.assertIn('width=1440:height=810', gfx[gfx.index('-i') + 1])
        dda = encoder_command(replace(settings, capture='ddagrab'), (1440, 810))
        filters = dda[dda.index('-vf') + 1]
        self.assertIn('scale=1440:810', filters)
        self.assertIn('pad=1440:810', filters)
        self.assertEqual(encoder_command(settings), encoder_command(settings, (1920, 1080)))
        mac = encoder_command(replace(settings, capture='avfoundation'), (1440, 810))
        self.assertIn('pad=1440:810', mac[mac.index('-vf') + 1])
        with self.assertRaisesRegex(ValueError, '1920x1080 only'):
            encoder_command(replace(settings, capture='screencapturekit'), (1440, 810))


class Device(list):
    """A fake PyUSB device: a list of configurations, each a list of interfaces."""
    def __init__(self, interfaces, product=0x0020):
        super().__init__([interfaces])
        self.idProduct = product


class Iface:
    def __init__(self, number, endpoints, klass=(255, 67, 1)):
        self.bInterfaceNumber, self.bAlternateSetting = number, 0
        self.bInterfaceClass, self.bInterfaceSubClass, self.bInterfaceProtocol = klass
        self.endpoints = [SimpleNamespace(bEndpointAddress=a, bmAttributes=2, wMaxPacketSize=size)
                          for a, size in endpoints]

    def __iter__(self):
        return iter(self.endpoints)


class UsbLinkTests(unittest.TestCase):
    def test_v2_product_with_other_endpoint_addresses(self):
        device = Device([Iface(3, [(0x03, 512), (0x84, 512)]), Iface(4, [(0x02, 512), (0x83, 512)])], product=0x001f)
        selected, link = select_control_link([device])
        self.assertIs(selected, device)
        self.assertEqual((link.product_id, link.interface, link.endpoint_out, link.endpoint_in, link.packet_size),
                         (0x001f, 4, 0x02, 0x83, 512))
        _, video = select_control_link([device], interface=3)
        self.assertEqual((video.endpoint_out, video.endpoint_in), (0x03, 0x84))

    def test_unknown_product_needs_any_product(self):
        device = Device([Iface(4, [(0x04, 512), (0x85, 512)])], product=0x0021)
        with self.assertRaises(DeviceNotFoundError):
            select_control_link([device])
        _, link = select_control_link([device], product_ids=None)
        self.assertEqual(link.product_id, 0x0021)

    def test_two_in_or_two_out_endpoints_are_not_a_control_link(self):
        device = Device([Iface(4, [(0x84, 512), (0x85, 512)])])
        with self.assertRaises(DeviceNotFoundError):
            select_control_link([device])
        device = Device([Iface(4, [(0x04, 512), (0x85, 512)], klass=(255, 67, 2))])
        with self.assertRaises(DeviceNotFoundError):
            select_control_link([device])


class UnknownGoggles(FakeUsb):
    """Answers identity with a code the bridge does not know and accepts video at 14/1."""
    def __init__(self, stop):
        super().__init__(stop)
        self.identity_decoder = V1Stream()
        self.video_receivers = []

    def write(self, data):
        for request in self.identity_decoder.feed(data):
            if (request.command_set, request.command_id) == (0, 255):
                self.incoming.put(answer(request, b'\0GL170 AC Jan 01 2024|00:00:00').serialize())
            else:
                if (request.command_set, request.command_id) == (11, 83):
                    self.video_receivers.append((request.receiver_type, request.receiver_id))
                super().write(request.serialize())


class EngineModelTests(EngineTests):
    def test_assumed_v2_profile_drives_size_and_route(self):
        stop = threading.Event()
        usbs = []
        def factory(_dll):
            usb = UnknownGoggles(stop)
            usbs.append(usb)
            return usb
        events, _ = self.run_case(factory, stop, encoder_factory=lambda: FakeEncoder(framed=True),
                                  settings=self.settings(assume_model='DJI FPV Goggles V2'))
        ready = next(e for e in events if e['event'] == 'ready')
        self.assertEqual((ready['model'], ready['resolution'], ready['tested']), ('DJI FPV Goggles V2', '1440x810', False))
        self.assertTrue(usbs[0].video_receivers)
        self.assertEqual(set(usbs[0].video_receivers), {(14, 1)})
        starting = next(e for e in events if e['event'] == 'starting')
        self.assertEqual(starting['resolution'], '1440x810')

    def test_known_goggles_keep_the_default_route(self):
        stop = threading.Event()
        usbs = []
        def factory(_dll):
            usb = FakeUsb(stop)
            usbs.append(usb)
            return usb
        events, _ = self.run_case(factory, stop)
        ready = next(e for e in events if e['event'] == 'ready')
        self.assertEqual((ready['resolution'], ready['tested']), ('1920x1080', True))
        self.assertEqual({(p.receiver_type, p.receiver_id) for p in usbs[0].video}, {(28, 1)})


# Only the model-specific tests belong to this module; the inherited engine tests run in their own file.
for _name in list(vars(EngineTests)):
    if _name.startswith('test_'):
        setattr(EngineModelTests, _name, None)
        delattr(EngineModelTests, _name)


if __name__ == '__main__':
    unittest.main()
