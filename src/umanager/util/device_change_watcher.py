from __future__ import annotations

import threading
import time
from typing import Optional

import pythoncom  # type: ignore
import wmi
from PySide6 import QtCore


class UsbDeviceChangeWatcher(QtCore.QObject):
    deviceChangeDetected = QtCore.Signal()

    def __init__(self, *, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def _run(self) -> None:
        pythoncom.CoInitialize()
        try:
            provider = wmi.WMI()
            watcher = provider.watch_for(
                notification_type="Creation",
                wmi_class="Win32_VolumeChangeEvent",
            )

            while not self._stop_event.is_set():
                try:
                    _event = watcher(timeout_ms=250)
                except wmi.x_wmi_timed_out:
                    continue
                except Exception:
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)
                    continue

                self.deviceChangeDetected.emit()
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="UsbDeviceChangeWatcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._started:
            return
        self._stop_event.set()

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)

        self._thread = None
        self._started = False
