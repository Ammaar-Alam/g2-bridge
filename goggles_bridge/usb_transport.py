"""Access the goggles' PC USB interface on Windows, macOS, or Linux.

Windows uses DJI's x64 driver 5.0.0.7, which binds the bulk interface of Goggles 2
(product 0020) and FPV Goggles V2 (product 001f). The backend checks the DLL hash before
using its device structure layout. Installing the driver places
libusb0_device.dll in System32. macOS binds no driver to the vendor interface,
so libusb-1.0 claims it directly. Linux also uses libusb-1.0, and the udev
rule in scripts/linux/60-dji-goggles.rules gives the user access to the device.
"""
import ctypes as C
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sys

from .models import PRODUCT_IDS

VERIFIED_DLL_SHA256 = 'd2c16bd7c7fb2344408259fd083c8fdbeda3b096b8c9d07e48848e99fc2c3743'
USB_WRITE_SIZES = (2048, 16384)
DEFAULT_DLL = Path(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'libusb0_device.dll')


class UsbTransportError(RuntimeError):
    """The current USB session cannot continue."""


class DeviceNotFoundError(UsbTransportError):
    """The supported USB interface is not attached."""


class LinkSpeedError(UsbTransportError):
    """The USB link is full-speed (12 Mbps), which is too slow for video."""


LINUX_UDEV_HINT = ('Install the udev rule: sudo cp scripts/linux/60-dji-goggles.rules /etc/udev/rules.d/ '
                   '&& sudo udevadm control --reload && sudo udevadm trigger. Over SSH, '
                   'also join the plugdev group')


@dataclass(frozen=True)
class ControlLink:
    """The USB interface and endpoints the bridge talks DUML over."""
    product_id: int
    interface: int
    endpoint_out: int
    endpoint_in: int
    packet_size: int


def select_control_link(devices, *, interface=4, product_ids=PRODUCT_IDS):
    """Return (device, ControlLink) for the one device with a DJI bulk control interface.

    The control interface is vendor class ff/43/01 with one bulk OUT and one bulk IN
    endpoint. It is interface 4 on Goggles 2 (product 0020), and DJI's own bulk driver
    binds interface 4 on the FPV Goggles V2 (product 001f) as well; the endpoint
    addresses are read from the descriptor rather than assumed. Goggles 2 links at high
    speed (512-byte bulk packets); a full-speed link is refused as too slow.
    """
    candidates = []
    for device in devices:
        product = getattr(device, 'idProduct', 0x0020)
        if product_ids is not None and product not in product_ids:
            continue
        for config in device:
            for candidate in config:
                if (candidate.bInterfaceNumber != interface or candidate.bAlternateSetting != 0
                        or (candidate.bInterfaceClass, candidate.bInterfaceSubClass,
                            candidate.bInterfaceProtocol) != (255, 67, 1)):
                    continue
                endpoints = list(candidate)
                outs = [e for e in endpoints if e.bmAttributes & 3 == 2 and not e.bEndpointAddress & 0x80]
                ins = [e for e in endpoints if e.bmAttributes & 3 == 2 and e.bEndpointAddress & 0x80]
                if (len(endpoints) == 2 and len(outs) == 1 and len(ins) == 1
                        and outs[0].wMaxPacketSize == ins[0].wMaxPacketSize
                        and outs[0].wMaxPacketSize in (64, 512)):
                    candidates.append((device, ControlLink(product, interface, outs[0].bEndpointAddress,
                                                           ins[0].bEndpointAddress, outs[0].wMaxPacketSize)))
    if not candidates:
        raise DeviceNotFoundError('Waiting for powered goggles in Virtual Flight mode')
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one DJI control interface; found {len(candidates)}')
    device, link = candidates[0]
    if link.packet_size == 64:
        raise LinkSpeedError('USB link is full-speed (12 Mbps), too slow for this stream. '
                             'Reconnect the data cable; try another port or cable if it recurs.')
    return device, link


def _select_control_device(devices):
    """Return the one device whose interface 4 matches the control interface."""
    return select_control_link(devices)[0]


def _windows_backend(dll_path):
    if C.sizeof(C.c_void_p) != 8:
        raise RuntimeError('This verified backend requires 64-bit Windows Python')
    dll = Path(dll_path).resolve(strict=True)
    if hashlib.sha256(dll.read_bytes()).hexdigest() != VERIFIED_DLL_SHA256:
        raise ValueError(f'Unsupported DJI USB DLL at {dll}. Install DJI driver 5.0.0.7 from DJI Assistant 2')
    import usb.backend.libusb0 as libusb
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
    return Backend()


def _libusb1_backend(install_hint):
    import usb.backend.libusb1 as libusb
    backend = libusb.get_backend()
    if backend is None:
        raise RuntimeError(f'Cannot load libusb. {install_hint}')
    return backend


def get_backend(dll_path=None):
    """Return the PyUSB backend for this platform."""
    if sys.platform == 'win32':
        return _windows_backend(dll_path)
    if sys.platform == 'darwin':
        return _libusb1_backend('Run "brew install libusb"')
    if sys.platform.startswith('linux'):
        return _libusb1_backend('Install libusb-1.0, for example "sudo apt install libusb-1.0-0"')
    raise RuntimeError('Goggles USB access requires Windows, macOS, or Linux')


class ControlUsb:
    def __init__(self, dll_path=None, *, write_size=2048, interface=4, product_ids=PRODUCT_IDS):
        if type(write_size) is not int or write_size not in USB_WRITE_SIZES:
            raise ValueError(f'Unsupported USB write size: {write_size}')
        if type(interface) is not int or not 0 <= interface < 32:
            raise ValueError('interface must be a USB interface number from 0 to 31')
        self.write_size = write_size
        backend = get_backend(dll_path)
        import usb.core
        import usb.util
        self.core = usb.core
        self.util = usb.util
        try:
            devices = usb.core.find(find_all=True, backend=backend, idVendor=0x2ca3)
            self.device, self.link = select_control_link(devices, interface=interface, product_ids=product_ids)
        except usb.core.USBError as exc:
            raise UsbTransportError(str(exc)) from exc
        self.closed = False
        try:
            if sys.platform.startswith('linux') and self.device.is_kernel_driver_active(self.link.interface):
                self.device.detach_kernel_driver(self.link.interface)
            self.util.claim_interface(self.device, self.link.interface)
        except usb.core.USBError as exc:
            self.util.dispose_resources(self.device)
            self.closed = True
            if sys.platform.startswith('linux') and exc.errno == 13:
                raise UsbTransportError(f'{exc}. {LINUX_UDEV_HINT}') from exc
            raise UsbTransportError(str(exc)) from exc

    def read(self, timeout_ms=100):
        if self.closed:
            raise RuntimeError('USB transport is closed')
        try:
            return bytes(self.device.read(self.link.endpoint_in, 4096, timeout=timeout_ms))
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
                written = self.device.write(self.link.endpoint_out, chunk, timeout=500)
            except self.core.USBError as exc:
                raise UsbTransportError(str(exc)) from exc
            if written != len(chunk):
                raise UsbTransportError(f'Short USB write: {written}/{len(chunk)}')

    def close(self):
        if not self.closed:
            try:
                try:
                    self.util.release_interface(self.device, self.link.interface)
                except self.core.USBError:
                    pass
                self.util.dispose_resources(self.device)
            finally:
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
