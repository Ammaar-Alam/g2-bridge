from dataclasses import replace
import unittest
from goggles_bridge.control import V1Packet
from goggles_bridge.session import ControlSession, SessionError


def answer(request, payload=b'\0'):
    return replace(request, sender_type=request.receiver_type, sender_id=request.receiver_id,
                   receiver_type=request.sender_type, receiver_id=request.sender_id,
                   is_response=1, ack=2, payload=payload)


class SessionTests(unittest.TestCase):
    def test_observed_exchange(self):
        session = ControlSession(sequence=0x6000)
        hb, = session.poll(0)
        self.assertEqual(hb.serialize().hex(), '551304032a1c00604000000000200000007b4f')
        info, = session.receive(V1Packet.parse(bytes.fromhex('5514046d1c2a0060c00000000000200000006d40')), .01)
        self.assertEqual(info.serialize().hex(), '550e04662a3c01604000ff0098ea')
        mode, = session.receive(V1Packet.parse(bytes.fromhex('552f04633c2a0160c000ff00453354205a563930302041432044656320323420323032347c31323a33343a3034141c')), .02)
        self.assertEqual(mode.serialize().hex(), '551104922a1c0260400b1a010100009dcc')
        session.receive(V1Packet.parse(bytes.fromhex('550e04661c2a0260c00b1a003168')), .03)
        self.assertEqual(session.state, 'ready')
        self.assertTrue(session.identity.startswith('E3T ZV900'))

    def test_wrong_route_and_sequence_cannot_unlock_video(self):
        session = ControlSession()
        request, = session.poll(0)
        for invalid in (replace(answer(request), sequence=1), replace(answer(request), receiver_type=2), replace(answer(request), command_id=255)):
            self.assertEqual(session.receive(invalid, .01), [])
        self.assertEqual(session.state, 'heartbeat')

    def test_rejected_identity_and_error_code(self):
        for payload in (b'\0E3T ZV902', b'\xe0'):
            session = ControlSession()
            request, = session.poll(0)
            info, = session.receive(answer(request), .01)
            with self.assertRaises(SessionError):
                session.receive(answer(info, payload), .02)
            self.assertEqual(session.state, 'failed')

    def test_bounded_retry_and_disconnect(self):
        session = ControlSession(sequence=65535)
        request, = session.poll(0)
        info, = session.receive(answer(request), .01)
        self.assertEqual(info.sequence, 0)
        for now in (.51, 1.01):
            due = session.poll(now)
            self.assertIn(info, due)
            hb = next(p for p in due if p.command_id == 0)
            session.receive(answer(hb), now+.01)
        with self.assertRaises(SessionError):
            session.poll(1.52)
        session = ControlSession()
        request, = session.poll(0)
        session.receive(answer(request), .01)
        with self.assertRaises(SessionError):
            session.poll(1.51)

    def test_mobile_address_is_explicit(self):
        session = ControlSession(source_type=2, source_id=0)
        request, = session.poll(0)
        self.assertEqual(request.serialize()[4], 2)
