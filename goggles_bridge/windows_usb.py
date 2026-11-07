"""Access the Goggles 2 USB interface through DJI's x64 driver 5.0.0.7.

The backend checks the DLL hash before using its device structure layout.
Obtain libusb0_device.dll separately from DJI Assistant.
"""
import ctypes as C
import hashlib
from pathlib import Path
import sys

VERIFIED_DLL_SHA256 = 'd2c16bd7c7fb2344408259fd083c8fdbeda3b096b8c9d07e48848e99fc2c3743'
USB_WRITE_SIZES = (2048, 16384)


class UsbTransportError(RuntimeError):
    """The current USB session cannot continue."""


class DeviceNotFoundError(UsbTransportError):
    """The supported USB interface is not attached."""


class LinkSpeedError(UsbTransportError):
    """The USB link is full-speed (12 Mbps), which is too slow for video."""


def _select_control_device(devices):
    candidates = []
    for device in devices:
        for config in device:
            for interface in config:
                if (interface.bInterfaceNumber != 4 or interface.bAlternateSetting != 0
                        or (interface.bInterfaceClass, interface.bInterfaceSubClass,
                            interface.bInterfaceProtocol) != (255, 67, 1)):
                    continue
                endpoints = list(interface)
                if (len(endpoints) == 2
                        and {(e.bEndpointAddress, e.bmAttributes) for e in endpoints} == {(4, 2), (0x85, 2)}
                        and len({e.wMaxPacketSize for e in endpoints}) == 1
                        and endpoints[0].wMaxPacketSize in (64, 512)):
                    candidates.append((device, endpoints[0].wMaxPacketSize))
    if not candidates:
        raise DeviceNotFoundError('Waiting for powered Goggles 2 in Virtual Flight mode')
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one DJI control interface; found {len(candidates)}')
    device, packet_size = candidates[0]
    if packet_size == 64:
        raise LinkSpeedError('USB link is full-speed (12 Mbps), too slow for this stream. '
                             'Reconnect the data cable; try another port or cable if it recurs.')
    return device


class WindowsControlUsb:
    def __init__(self, dll_path, *, write_size=2048):
        if type(write_size) is not int or write_size not in USB_WRITE_SIZES:
            raise ValueError(f'Unsupported USB write size: {write_size}')
        self.write_size = write_size
        if sys.platform != 'win32' or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('This verified backend requires 64-bit Windows Python')
        dll = Path(dll_path).resolve(strict=True)
        if hashlib.sha256(dll.read_bytes()).hexdigest() != VERIFIED_DLL_SHA256:
            raise ValueError('Unverified DJI DLL: its structure layout may differ')
        import usb.core
        import usb.util
        import usb.backend.libusb0 as libusb
        self.core = usb.core
        self.util = usb.util
        if libusb.get_backend(find_library=lambda _: str(dll)) is None:
            raise RuntimeError('Cannot load the verified DJI USB DLL')
        if Path(libusb._lib._name).resolve() != dll:
            raise RuntimeError('A different libusb0 DLL is already loaded in this process')

        class DjiDevice(C.Structure):
            _pack_ = 1

        DjiDevice._fields_ = [
            ('next', C.POINTER(DjiDevice)), ('prev', C.POINTER(DjiDevice)),
            ('filename', C.c_char * 512), ('location', C.c_char * 512),
            ('bus', C.POINTER(libusb._usb_bus)), ('descriptor', libusb._usb_device_descriptor),
            ('config', C.POINTER(libusb._usb_config_descriptor)), ('dev', C.c_void_p),
            ('devnum', C.c_uint8), ('num_children', C.c_uint8),
            ('children', C.POINTER(C.POINTER(DjiDevice))),
        ]
        assert DjiDevice.descriptor.offset == 1048 and C.sizeof(DjiDevice) == 1092

        class Backend(libusb._LibUSB):
            def enumerate_devices(self):
                for device in super().enumerate_devices():
                    yield C.cast(C.pointer(device), C.POINTER(DjiDevice)).contents

        libusb._lib.usb_open.argtypes = [C.POINTER(DjiDevice)]
        try:
            devices = usb.core.find(find_all=True, backend=Backend(), idVendor=0x2ca3, idProduct=0x0020)
            self.device = _select_control_device(devices)
        except usb.core.USBError as exc:
            raise UsbTransportError(str(exc)) from exc
        self.closed = False
        try:
            self.util.claim_interface(self.device, 4)
        except usb.core.USBError as exc:
            self.util.dispose_resources(self.device)
            self.closed = True
            raise UsbTransportError(str(exc)) from exc

    def read(self, timeout_ms=100):
        if self.closed:
            raise RuntimeError('USB transport is closed')
        try:
            return bytes(self.device.read(0x85, 4096, timeout=timeout_ms))
        except self.core.USBError as exc:
            if isinstance(exc, self.core.USBTimeoutError) or exc.backend_error_code == -116:
                return b''
            raise UsbTransportError(str(exc)) from exc

    def write(self, data):
        if self.closed:
            raise RuntimeError('USB transport is closed')
        data = bytes(data)
        for offset in range(0, len(data), self.write_size):
            chunk = data[offset:offset+self.write_size]
            try:
                written = self.device.write(4, chunk, timeout=500)
            except self.core.USBError as exc:
                raise UsbTransportError(str(exc)) from exc
            if written != len(chunk):
                raise UsbTransportError(f'Short USB write: {written}/{len(chunk)}')

    def close(self):
        if not self.closed:
            try:
                self.util.dispose_resources(self.device)
            finally:
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
