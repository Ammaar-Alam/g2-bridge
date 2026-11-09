"""Talk DUML to goggles that expose a USB virtual COM port, such as the FPV Goggles V2.

On the FPV Goggles V2 (USB 2ca3:001f), DJI's driver binds interface 4 as
"DEVICE USB Virtual COM", so the PC reaches the goggles' DUML modules through a
serial port rather than a libusb bulk interface. This transport has the same
read/write/close surface as ControlUsb, so the session, probe and engine can use
either. It needs pyserial.
"""
import sys

from .usb_transport import DeviceNotFoundError, UsbTransportError

DJI_VENDOR_ID = 0x2ca3


def _serial():
    try:
        import serial
        import serial.tools.list_ports
    except ImportError as exc:
        raise RuntimeError('pyserial is required for the serial transport: python -m pip install pyserial') from exc
    return serial


def list_dji_ports(product_ids=None):
    """Return pyserial port infos for DJI virtual COM ports, newest interface first."""
    serial = _serial()
    ports = []
    for info in serial.tools.list_ports.comports():
        if info.vid != DJI_VENDOR_ID:
            continue
        if product_ids is not None and info.pid not in product_ids:
            continue
        ports.append(info)
    return sorted(ports, key=lambda p: p.device)


def find_dji_port(product_ids=None):
    """Return the device name of the one DJI virtual COM port, or raise."""
    ports = list_dji_ports(product_ids)
    if not ports:
        raise DeviceNotFoundError('No DJI virtual COM port found. Power the goggles and connect a data cable; '
                                  'close DJI Assistant, which holds the port while it runs')
    if len(ports) > 1:
        names = ', '.join(f'{p.device} ({p.pid:04x})' for p in ports)
        raise RuntimeError(f'Expected one DJI virtual COM port; found {names}. Pass --serial PORT')
    return ports[0].device


class ControlSerial:
    """Byte transport over a virtual COM port with the ControlUsb read/write surface."""
    def __init__(self, port=None, *, write_size=16384, product_ids=None, baudrate=115200):
        serial = _serial()
        self.port = port or find_dji_port(product_ids)
        self.write_size = write_size
        try:
            # The baud rate is nominal over USB CDC; timeouts are set per read
            self.handle = serial.Serial(self.port, baudrate=baudrate, timeout=.05, write_timeout=.5)
        except serial.SerialException as exc:
            text = str(exc)
            if 'denied' in text.lower() or 'PermissionError' in text:
                text += '. Another program has the port open; close DJI Assistant and its DJIService'
            raise UsbTransportError(text) from exc
        self.serial_module = serial
        self.closed = False
        self.link = None  # No USB link details; kept for callers that log them

    def read(self, timeout_ms=100):
        if self.closed:
            raise RuntimeError('Serial transport is closed')
        try:
            self.handle.timeout = max(timeout_ms, 1) / 1000
            waiting = self.handle.in_waiting
            data = self.handle.read(max(waiting, 1))
            if waiting > 1:
                return data
            # Drain anything that arrived while waiting for the first byte
            more = self.handle.in_waiting
            return data + (self.handle.read(more) if more else b'')
        except self.serial_module.SerialException as exc:
            raise UsbTransportError(str(exc)) from exc

    def write(self, data):
        if self.closed:
            raise RuntimeError('Serial transport is closed')
        data = bytes(data)
        for offset in range(0, len(data), self.write_size):
            chunk = data[offset:offset + self.write_size]
            try:
                written = self.handle.write(chunk)
            except self.serial_module.SerialException as exc:
                raise UsbTransportError(str(exc)) from exc
            if written != len(chunk):
                raise UsbTransportError(f'Short serial write: {written}/{len(chunk)}')

    def close(self):
        if not self.closed:
            try:
                self.handle.close()
            finally:
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def default_port_hint():
    return 'COM port such as COM10' if sys.platform == 'win32' else '/dev/ttyACM0 or /dev/cu.usbmodem*'
