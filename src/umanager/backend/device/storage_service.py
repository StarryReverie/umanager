from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import wmi

from .base_service import UsbBaseDeviceService
from .protocol import (
    UsbDeviceId,
    UsbStorageDeviceInfo,
    UsbStorageDeviceProtocol,
    UsbVolumeInfo,
)


class _WmiDiskDrive(Protocol):
    PNPDeviceID: str


class _PnPEntity(Protocol):
    PNPDeviceID: str
    HardwareID: Optional[list[str]]


class _WmiDiskPartition(Protocol):
    pass


class _WmiLogicalDisk(Protocol):
    DeviceID: Optional[str]
    FileSystem: Optional[str]
    VolumeName: Optional[str]
    Size: Optional[str]
    FreeSpace: Optional[str]


@dataclass(frozen=True, slots=True)
class _StorageScanResult:
    device_ids: list[UsbDeviceId]
    volumes_by_instance_id: dict[str, list[UsbVolumeInfo]]


class UsbStorageDeviceService(UsbStorageDeviceProtocol):
    _wmi_provider = wmi.WMI()
    _base_device_service: UsbBaseDeviceService
    _cached_device_ids: list[UsbDeviceId]
    _cached_volumes_by_instance_id: dict[str, list[UsbVolumeInfo]]
    _cached_disk_drives: list[_WmiDiskDrive]

    def __init__(self, base_device_service: UsbBaseDeviceService) -> None:
        self._base_device_service = base_device_service
        self._cached_device_ids = []
        self._cached_volumes_by_instance_id = {}
        self._cached_disk_drives = []

    def refresh(self) -> None:
        self._base_device_service.refresh()

        self._cached_disk_drives = self._scan_disk_drives_uncached()

        scan = self._scan_storage_devices_uncached()
        self._cached_device_ids = scan.device_ids
        self._cached_volumes_by_instance_id = scan.volumes_by_instance_id

    def get_disk_drives(self) -> list[_WmiDiskDrive]:
        return self._cached_disk_drives

    def list_storage_device_ids(self) -> list[UsbDeviceId]:
        res = list(self._cached_device_ids)
        res.sort(key=lambda d: d.instance_id.casefold())
        return res

    def get_storage_device_info(self, device_id: UsbDeviceId) -> UsbStorageDeviceInfo:
        if not any(d.instance_id == device_id.instance_id for d in self._cached_device_ids):
            raise FileNotFoundError(f"USB storage device not found: {device_id.instance_id}")

        base = self._base_device_service.get_base_device_info(device_id)
        volumes = list(self._cached_volumes_by_instance_id.get(device_id.instance_id, []))
        return UsbStorageDeviceInfo(base=base, volumes=volumes)

    def _scan_storage_devices_uncached(self) -> _StorageScanResult:
        entities = self._base_device_service.get_usb_pnp_entities()

        storage_instance_ids: list[str] = []
        for e in entities:
            instance_id = getattr(e, "PNPDeviceID", None)
            if not instance_id:
                continue
            if self._is_storage_pnp_entity(e):
                storage_instance_ids.append(instance_id)

        device_ids: list[UsbDeviceId] = []
        volumes_by_instance_id: dict[str, list[UsbVolumeInfo]] = {}

        disk_volume_map: dict[str, list[UsbVolumeInfo]] = {}
        for disk in self._iter_usb_disk_drives():
            instance_id = getattr(disk, "PNPDeviceID", None)
            if not instance_id:
                continue
            disk_volume_map[instance_id] = self._get_volumes_for_disk(disk)

        for instance_id in storage_instance_ids:
            device_ids.append(UsbDeviceId(instance_id=instance_id))
            volumes_by_instance_id[instance_id] = list(disk_volume_map.get(instance_id, []))

        return _StorageScanResult(
            device_ids=device_ids,
            volumes_by_instance_id=volumes_by_instance_id,
        )

    def _is_storage_pnp_entity(self, entity: _PnPEntity) -> bool:
        instance_id = str(getattr(entity, "PNPDeviceID", "") or "")
        if instance_id.upper().startswith("USBSTOR\\"):
            return True

        hardware_ids = getattr(entity, "HardwareID", None) or []
        for hid in hardware_ids:
            if str(hid).upper().startswith("USBSTOR\\"):
                return True

        return False

    def _iter_usb_disk_drives(self) -> list[_WmiDiskDrive]:
        disks = self.get_disk_drives()

        res: list[_WmiDiskDrive] = []
        for d in disks:
            pnp = str(getattr(d, "PNPDeviceID", "") or "")
            if not pnp:
                continue

            if pnp.upper().startswith("USBSTOR\\"):
                res.append(d)

        return res

    def _scan_disk_drives_uncached(self) -> list[_WmiDiskDrive]:
        try:
            return list(self._wmi_provider.Win32_DiskDrive())
        except Exception:
            return []

    def _get_volumes_for_disk(self, disk: _WmiDiskDrive) -> list[UsbVolumeInfo]:
        volumes: list[UsbVolumeInfo] = []

        try:
            partitions = disk.associators("Win32_DiskDriveToDiskPartition")  # type: ignore[attr-defined]
        except Exception:
            partitions = []

        for part in partitions or []:
            volumes.extend(self._get_volumes_for_partition(part))

        volumes.sort(key=lambda v: (v.drive_letter or "").casefold())
        return volumes

    def _get_volumes_for_partition(self, partition: _WmiDiskPartition) -> list[UsbVolumeInfo]:
        logical_disks: list[_WmiLogicalDisk]
        try:
            logical_disks = list(
                partition.associators("Win32_LogicalDiskToPartition")  # type: ignore[attr-defined]
            )
        except Exception:
            logical_disks = []

        res: list[UsbVolumeInfo] = []
        for ld in logical_disks:
            drive = getattr(ld, "DeviceID", None)
            if drive:
                mount_path = Path(f"{drive}\\")
            else:
                mount_path = None

            total_bytes = self._parse_optional_int(getattr(ld, "Size", None))
            free_bytes = self._parse_optional_int(getattr(ld, "FreeSpace", None))

            res.append(
                UsbVolumeInfo(
                    drive_letter=drive,
                    mount_path=mount_path,
                    file_system=getattr(ld, "FileSystem", None),
                    volume_label=getattr(ld, "VolumeName", None),
                    total_bytes=total_bytes,
                    free_bytes=free_bytes,
                )
            )

        return res

    def _parse_optional_int(self, value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            s = str(value).strip()
            if not s:
                return None
            return int(s)
        except Exception:
            return None
