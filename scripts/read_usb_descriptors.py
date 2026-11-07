"""Read DJI USB descriptors through the Windows hub driver without changing drivers."""

import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import uuid


def parse_configuration(data):
    if len(data) < 9 or data[0:2] != b'\x09\x02':
        raise ValueError('Missing USB configuration descriptor')
    total = struct.unpack_from('<H', data, 2)[0]
    if total != len(data):
        raise ValueError('Configuration length does not match descriptor bytes')
    result = {'configuration_value': data[5], 'interface_count': data[4], 'interfaces': []}
    offset, interface = 0, None
    while offset < total:
        if offset + 2 > total:
            raise ValueError('Truncated descriptor header')
        length, kind = data[offset:offset+2]
        if length < 2 or offset + length > total:
            raise ValueError('Invalid descriptor length')
        item = data[offset:offset+length]
        if kind == 4:
            if length < 9:
                raise ValueError('Truncated interface descriptor')
            interface = dict(number=item[2], alternate=item[3], endpoint_count=item[4],
                             usb_class=item[5], subclass=item[6], protocol=item[7], endpoints=[])
            result['interfaces'].append(interface)
        elif kind == 5:
            if length < 7 or interface is None:
                raise ValueError('Invalid endpoint descriptor')
            interface['endpoints'].append(dict(address=f'0x{item[2]:02x}',
                direction='in' if item[2] & 0x80 else 'out', transfer_type=item[3] & 3,
                max_packet_size=struct.unpack_from('<H', item, 4)[0], interval=item[6]))
        offset += length
    for interface in result['interfaces']:
        if interface['endpoint_count'] != len(interface['endpoints']):
            raise ValueError('Interface endpoint count mismatch')
    return result


def read_windows_devices():
    if sys.platform != 'win32':
        raise RuntimeError('USB inventory requires Windows')
    setup = c.WinDLL('setupapi', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    guid = (c.c_ubyte * 16).from_buffer_copy(uuid.UUID('f18a0e88-c30c-11d0-8815-00a0c906bed8').bytes_le)

    class InterfaceData(c.Structure):
        _fields_ = [('size', w.DWORD), ('guid', c.c_ubyte * 16), ('flags', w.DWORD), ('reserved', c.c_size_t)]

    setup.SetupDiGetClassDevsW.argtypes = [c.c_void_p, w.LPCWSTR, w.HWND, w.DWORD]
    setup.SetupDiGetClassDevsW.restype = w.HANDLE
    setup.SetupDiEnumDeviceInterfaces.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(InterfaceData)]
    setup.SetupDiEnumDeviceInterfaces.restype = w.BOOL
    setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [w.HANDLE, c.POINTER(InterfaceData), c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
    setup.SetupDiGetDeviceInterfaceDetailW.restype = w.BOOL
    setup.SetupDiDestroyDeviceInfoList.argtypes = [w.HANDLE]
    setup.SetupDiDestroyDeviceInfoList.restype = w.BOOL
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    kernel.DeviceIoControl.argtypes = [w.HANDLE, w.DWORD, c.c_void_p, w.DWORD, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
    kernel.DeviceIoControl.restype = w.BOOL
    invalid = c.c_void_p(-1).value

    def ioctl(handle, function, initial, size):
        buffer = c.create_string_buffer(size)
        c.memmove(buffer, initial, len(initial))
        returned = w.DWORD()
        if not kernel.DeviceIoControl(handle, (0x22 << 16) | (function << 2), buffer, size,
                                      buffer, size, c.byref(returned), None):
            raise c.WinError(c.get_last_error())
        return buffer.raw[:returned.value]

    def descriptor(handle, port, kind, length):
        request = struct.pack('<IBBHHH', port, 0x80, 6, kind << 8, 0, length)
        return ioctl(handle, 260, request, 12 + length)[12:]

    devices, errors = [], []
    device_set = setup.SetupDiGetClassDevsW(c.byref(guid), None, None, 0x12)
    if device_set == invalid:
        raise c.WinError(c.get_last_error())
    try:
        index = 0
        while True:
            interface = InterfaceData()
            interface.size = c.sizeof(interface)
            if not setup.SetupDiEnumDeviceInterfaces(device_set, None, c.byref(guid), index, c.byref(interface)):
                if c.get_last_error() == 259:
                    break
                raise c.WinError(c.get_last_error())
            index += 1
            needed = w.DWORD()
            setup.SetupDiGetDeviceInterfaceDetailW(device_set, c.byref(interface), None, 0, c.byref(needed), None)
            if c.get_last_error() != 122 or needed.value < 6:
                raise c.WinError(c.get_last_error())
            detail = c.create_string_buffer(needed.value)
            struct.pack_into('<I', detail, 0, 8 if c.sizeof(c.c_void_p) == 8 else 6)
            if not setup.SetupDiGetDeviceInterfaceDetailW(device_set, c.byref(interface), detail, needed, None, None):
                raise c.WinError(c.get_last_error())
            hub_path = c.wstring_at(c.addressof(detail) + 4)
            handle = kernel.CreateFileW(hub_path, 0, 3, None, 3, 0, None)
            if handle == invalid:
                errors.append({'hub': hub_path, 'error': str(c.WinError(c.get_last_error()))})
                continue
            try:
                hub = ioctl(handle, 258, bytes(76), 76)
                if len(hub) < 7:
                    raise ValueError('Truncated hub information')
                for port in range(1, hub[6] + 1):
                    info = ioctl(handle, 274, struct.pack('<I', port), 4096)
                    if len(info) < 35:
                        raise ValueError('Truncated connection information')
                    if struct.unpack_from('<I', info, 31)[0] != 1:
                        continue
                    vendor, product = struct.unpack_from('<HH', info, 12)
                    if vendor != 0x2ca3:
                        continue
                    header = descriptor(handle, port, 2, 9)
                    if len(header) != 9:
                        raise ValueError('Truncated configuration header')
                    length = struct.unpack_from('<H', header, 2)[0]
                    config = descriptor(handle, port, 2, length)
                    devices.append(dict(vendor_id=f'{vendor:04x}', product_id=f'{product:04x}',
                        hub=hub_path, port=port, usb_speed_code=info[23],
                        device_descriptor_hex=info[4:22].hex(), configuration_hex=config.hex(),
                        configuration=parse_configuration(config)))
            except (OSError, ValueError) as error:
                errors.append({'hub': hub_path, 'error': str(error)})
            finally:
                kernel.CloseHandle(handle)
    finally:
        setup.SetupDiDestroyDeviceInfoList(device_set)
    return {'captured_utc': datetime.now(timezone.utc).isoformat(), 'devices': devices, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    report = read_windows_devices()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(f"Saved {len(report['devices'])} DJI device(s); {len(report['errors'])} error(s)")
    return 1 if report['errors'] or not report['devices'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
