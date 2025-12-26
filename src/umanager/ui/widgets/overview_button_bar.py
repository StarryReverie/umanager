from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class OverviewButtonBarWidget(QWidget):
    """总览页按钮栏，水平布局，居右对齐。

    包含三个按钮：
    - 刷新：刷新设备列表
    - 查看具体信息：显示选中设备的详细信息
    - 安全弹出：安全移除选中设备
    """

    refresh_devices = Signal()
    view_details = Signal()
    eject_device = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._refresh_btn = QPushButton("刷新")
        self._view_details_btn = QPushButton("查看具体信息")
        self._eject_btn = QPushButton("安全弹出")

        # 连接信号
        self._refresh_btn.clicked.connect(self.refresh_devices.emit)
        self._view_details_btn.clicked.connect(self.view_details.emit)
        self._eject_btn.clicked.connect(self.eject_device.emit)

        # 布局：水平，居右
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()  # 填充左侧空间，使按钮右对齐
        layout.addWidget(self._refresh_btn)
        layout.addWidget(self._view_details_btn)
        layout.addWidget(self._eject_btn)

        self.setLayout(layout)

    def set_enabled(self, enabled: bool) -> None:
        """启用或禁用所有按钮。"""
        self._refresh_btn.setEnabled(enabled)
        self._view_details_btn.setEnabled(enabled)
        self._eject_btn.setEnabled(enabled)

    def set_refresh_enabled(self, enabled: bool) -> None:
        """单独启用或禁用刷新按钮。"""
        self._refresh_btn.setEnabled(enabled)

    def set_details_enabled(self, enabled: bool) -> None:
        """单独启用或禁用查看具体信息按钮。"""
        self._view_details_btn.setEnabled(enabled)

    def set_eject_enabled(self, enabled: bool) -> None:
        """单独启用或禁用安全弹出按钮。"""
        self._eject_btn.setEnabled(enabled)
