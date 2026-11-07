"""Bounded Goggles 2 control handshake, independent of the byte transport.

Ready means matched simulator-mode success, never proof of visible video.
The PC source address is observed live. The mobile route is recovered from
the app and still requires a custom-client hardware test.
"""
from dataclasses import dataclass, replace
from .control import heartbeat, device_info, sim_mode


class SessionError(RuntimeError):
    pass


class SessionLost(SessionError):
    """Retryable loss of control replies; device rejection remains fatal."""


@dataclass
class Pending:
    packet: object
    sent_at: float
    attempts: int = 1


class ControlSession:
    def __init__(self, *, source_type=10, source_id=1, sequence=0):
        # Validate addresses and sequence using the actual serializer.
        replace(heartbeat(sequence), sender_type=source_type, sender_id=source_id).serialize()
        self.source_type = source_type
        self.source_id = source_id
        self.sequence = sequence
        self.state = 'new'
        self.identity = None
        self.pending = {}
        self.started_at = None
        self.last_heartbeat_ack = None
        self.next_heartbeat = None

    def reserve_sequence(self):
        """Share the V1 counter with video without reusing pending requests."""
        if self.state == 'failed':
            raise SessionError('Session has failed; create a new one after reconnect')
        for _ in range(65536):
            sequence = self.sequence
            self.sequence = (self.sequence + 1) & 65535
            if sequence not in self.pending:
                return sequence
        raise SessionError('Sequence space exhausted')

    def _new(self, factory, now):
        sequence = self.reserve_sequence()
        packet = replace(factory(sequence), sender_type=self.source_type, sender_id=self.source_id)
        self.pending[sequence] = Pending(packet, now)
        return packet

    def _fail(self, message, error_type=SessionError):
        self.state = 'failed'
        self.pending.clear()
        raise error_type(message)

    def poll(self, now):
        """Return requests due at caller-supplied monotonic seconds."""
        if self.state == 'failed':
            raise SessionError('Session has failed; create a new one after reconnect')
        if self.started_at is None:
            self.started_at = now
            self.next_heartbeat = now
            self.state = 'heartbeat'
        if self.last_heartbeat_ack is not None and now - self.last_heartbeat_ack >= 1.5:
            self._fail('Three heartbeat intervals passed without a matching success reply', SessionLost)
        if self.state != 'ready' and now - self.started_at >= 4:
            self._fail('Control handshake timed out', SessionLost)
        outgoing = []
        for seq, item in list(self.pending.items()):
            if now - item.sent_at < .5:
                continue
            if (item.packet.command_set, item.packet.command_id) == (0, 0):
                # A fresh heartbeat below replaces this one.
                del self.pending[seq]
            elif item.attempts >= 3:
                self._fail('Control request received no response after three attempts', SessionLost)
            else:
                item.attempts += 1
                item.sent_at = now
                outgoing.append(item.packet)
        if now >= self.next_heartbeat:
            outgoing.append(self._new(heartbeat, now))
            self.next_heartbeat = now + .5
        return outgoing

    def receive(self, reply, now):
        """Accept a CRC-validated packet, returning any next handshake request."""
        if self.state == 'failed':
            return []
        pending = self.pending.get(reply.sequence)
        if pending is None or not reply.is_response:
            return []
        req = pending.packet
        if (reply.command_set, reply.command_id, reply.sender_type, reply.sender_id,
                reply.receiver_type, reply.receiver_id) != (
                req.command_set, req.command_id, req.receiver_type, req.receiver_id,
                req.sender_type, req.sender_id):
            return []
        del self.pending[reply.sequence]
        if reply.payload[:1] != b'\0':
            self._fail(f'Goggles rejected {req.command_set:02x}/{req.command_id:02x}: {reply.payload.hex()}')
        command = (reply.command_set, reply.command_id)
        if command == (0, 0):
            self.last_heartbeat_ack = now
            if self.state == 'heartbeat':
                self.state = 'identity'
                return [self._new(device_info, now)]
        elif command == (0, 255) and self.state == 'identity':
            self.identity = reply.payload[1:].rstrip(b'\0').decode('ascii', errors='replace')
            if b'ZV900' not in reply.payload.upper():
                self._fail('Device identity is not the verified ZV900 profile')
            self.state = 'simulator'
            return [self._new(sim_mode, now)]
        elif command == (11, 26) and self.state == 'simulator':
            self.state = 'ready'
        return []
