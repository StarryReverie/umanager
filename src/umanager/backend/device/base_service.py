from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol

import wmi

from .protocol import UsbBaseDeviceInfo, UsbBaseDeviceProtocol, UsbDeviceId


class _PnPEntity(Protocol):
    PNPDeviceID: str
    Name: Optional[str]
    Manufacturer: Optional[str]
    Description: Optional[str]


@dataclass(frozen=True, slots=True)
class _ParsedUsbIds:
    vendor_id: Optional[str]
    product_id: Optional[str]
    serial_number: Optional[str]


class UsbBaseDeviceService(UsbBaseDeviceProtocol):
    _VID_PATTERN = re.compile(r"VID_([0-9A-Fa-f]{4})")
    _PID_PATTERN = re.compile(r"PID_([0-9A-Fa-f]{4})")

    _wmi_provider = wmi.WMI()

    def list_base_device_ids(self) -> list[UsbDeviceId]:
        entities = self._scan_usb_pnp_entities()
        res = [UsbDeviceId(instance_id=e.PNPDeviceID) for e in entities]

        res.sort(key=lambda d: d.instance_id.casefold())
        return res

    def get_base_device_info(self, device_id: UsbDeviceId) -> UsbBaseDeviceInfo:
        entity: _PnPEntity | None = None
        for candidate in self._scan_usb_pnp_entities():
            if getattr(candidate, "PNPDeviceID", None) == device_id.instance_id:
                entity = candidate
                break
        if entity is None:
            raise FileNotFoundError(f"USB device not found: {device_id.instance_id}")

        parsed = self._parse_usb_ids(device_id.instance_id)
        manufacturer = getattr(entity, "Manufacturer", None)
        name = getattr(entity, "Name", None)
        description = getattr(entity, "Description", None)

        return UsbBaseDeviceInfo(
            id=device_id,
            vendor_id=parsed.vendor_id,
            product_id=parsed.product_id,
            manufacturer=manufacturer,
            product=name,
            serial_number=parsed.serial_number,
            description=description or name,
        )

    def _scan_usb_pnp_entities(self) -> list[_PnPEntity]:
        entities: list[_PnPEntity] = []

        for candidate in self._wmi_provider.Win32_PnPEntity():
            instance_id = getattr(candidate, "PNPDeviceID", None)
            if not instance_id:
                continue

            if str(instance_id).startswith("USB"):
                entities.append(candidate)

        return entities

    def _parse_usb_ids(self, instance_id: str) -> _ParsedUsbIds:
        vid_match = self._VID_PATTERN.search(instance_id)
        vendor_id = vid_match.group(1).upper() if vid_match else None

        pid_match = self._PID_PATTERN.search(instance_id)
        product_id = pid_match.group(1).upper() if pid_match else None

        serial_number: Optional[str] = None
        # Typical format: USB\\VID_XXXX&PID_YYYY\\<serial or location string>
        parts = instance_id.split(r"\\")
        if len(parts) >= 3 and parts[-1]:
            serial_number = parts[-1]

        return _ParsedUsbIds(
            vendor_id=vendor_id,
            product_id=product_id,
            serial_number=serial_number,
        )
