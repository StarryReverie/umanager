from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from ...backend.device import UsbBaseDeviceInfo, UsbStorageDeviceInfo, UsbVolumeInfo


class DeviceDetailDialog(QDialog):
    """显示 USB 设备详细信息的对话框（垂直逐行展示）。"""

    def __init__(
        self,
        base: UsbBaseDeviceInfo,
        storage: Optional[UsbStorageDeviceInfo] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设备详细信息")

        layout = QVBoxLayout(self)

        # 基础设备信息
        for label, value in self._build_base_lines(base):
            layout.addWidget(QLabel(f"{label}: {value}"))

        # 存储设备信息（若存在）
        if storage is not None:
            for line in self._build_storage_lines(storage):
                layout.addWidget(QLabel(line))

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok, parent=self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _fmt(val: object, default: str = "-") -> str:
        return str(val) if val not in (None, "") else default

    @staticmethod
    def _fmt_hex(val: Optional[str]) -> str:
        if val is None:
            return "-"
        # 确保统一前缀
        if val.lower().startswith("0x"):
            return val
        return f"0x{val}"

    @staticmethod
    def _fmt_speed(speed: Optional[float]) -> str:
        if speed is None:
            return "-"
        return f"{speed:.0f} Mbps"

    @staticmethod
    def _fmt_bytes(val: Optional[int]) -> str:
        if val is None:
            return "-"
        gb = val / (1024**3)
        return f"{gb:.1f} GB"

    def _build_base_lines(self, base: UsbBaseDeviceInfo) -> list[tuple[str, str]]:
        return [
            ("产品", self._fmt(base.product)),
            ("制造商", self._fmt(base.manufacturer)),
            ("序列号", self._fmt(base.serial_number)),
            ("厂商 ID", self._fmt_hex(base.vendor_id)),
            ("产品 ID", self._fmt_hex(base.product_id)),
            ("USB 版本", self._fmt(base.usb_version)),
            ("速度", self._fmt_speed(base.speed_mbps)),
            ("总线号", self._fmt(base.bus_number)),
            ("端口号", self._fmt(base.port_number)),
            ("描述", self._fmt(base.description)),
        ]

    def _build_storage_lines(self, storage: UsbStorageDeviceInfo) -> list[str]:
        lines: list[str] = []
        for idx, vol in enumerate(storage.volumes):
            prefix = f"卷 {idx + 1}"
            lines.append(
                f"{prefix}: 卷标={self._fmt(vol.volume_label)} | "
                f"文件系统={self._fmt(vol.file_system)} | "
                f"挂载={self._fmt(self._format_mount(vol))}"
            )
            lines.append(f"{prefix}: 剩余/容量={self._format_capacity(vol)}")
        if not lines:
            lines.append("存储卷信息: -")
        return lines

    def _format_capacity(self, vol: UsbVolumeInfo) -> str:
        if vol.free_bytes is not None and vol.total_bytes is not None:
            return f"{self._fmt_bytes(vol.free_bytes)}/{self._fmt_bytes(vol.total_bytes)}"
        if vol.total_bytes is not None:
            return f"-/ {self._fmt_bytes(vol.total_bytes)}"
        return "-/-"

    @staticmethod
    def _format_mount(vol: UsbVolumeInfo) -> str:
        if vol.drive_letter:
            return vol.drive_letter
        if vol.mount_path:
            return str(vol.mount_path)
        return "-"
