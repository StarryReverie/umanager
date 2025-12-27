from __future__ import annotations

from typing import Any, Callable, Optional

import pytest
from PySide6 import QtCore

from umanager.backend.device import (
    DeviceEjectResult,
    UsbBaseDeviceInfo,
    UsbBaseDeviceProtocol,
    UsbDeviceId,
    UsbStorageDeviceInfo,
    UsbStorageDeviceProtocol,
)
from umanager.ui.states import MainAreaState, MainAreaStateManager


class FakeBaseDeviceService(UsbBaseDeviceProtocol):
    def __init__(self) -> None:
        self._ids: list[UsbDeviceId] = []
        self._info: dict[str, UsbBaseDeviceInfo] = {}
        self.refresh_calls = 0
        self.raise_on_refresh: Optional[Exception] = None

    def add_device(self, instance_id: str, *, product: str = "Device") -> UsbBaseDeviceInfo:
        dev_id = UsbDeviceId(instance_id=instance_id)
        info = UsbBaseDeviceInfo(id=dev_id, product=product)
        self._ids.append(dev_id)
        self._info[instance_id] = info
        return info

    def refresh(self) -> None:
        self.refresh_calls += 1
        if self.raise_on_refresh is not None:
            raise self.raise_on_refresh

    def get_base_device_info(self, device_id: UsbDeviceId) -> UsbBaseDeviceInfo:
        return self._info[device_id.instance_id]

    def list_base_device_ids(self) -> list[UsbDeviceId]:
        return list(self._ids)


class FakeStorageDeviceService(UsbStorageDeviceProtocol):
    def __init__(self, base: FakeBaseDeviceService) -> None:
        self._base = base
        self._storage_ids: list[UsbDeviceId] = []
        self.refresh_calls = 0
        self.raise_on_refresh: Optional[Exception] = None
        self.raise_on_get_info: set[str] = set()

        self.eject_calls: list[str] = []
        self.next_eject_result: Optional[DeviceEjectResult] = None
        self.raise_on_eject: Optional[Exception] = None

    def add_storage(self, instance_id: str) -> None:
        dev_id = UsbDeviceId(instance_id=instance_id)
        if instance_id not in {i.instance_id for i in self._storage_ids}:
            self._storage_ids.append(dev_id)

    def refresh(self) -> None:
        self.refresh_calls += 1
        if self.raise_on_refresh is not None:
            raise self.raise_on_refresh

    def get_storage_device_info(self, device_id: UsbDeviceId) -> UsbStorageDeviceInfo:
        if device_id.instance_id in self.raise_on_get_info:
            raise RuntimeError("storage info failed")
        base_info = self._base.get_base_device_info(device_id)
        return UsbStorageDeviceInfo(base=base_info)

    def list_storage_device_ids(self) -> list[UsbDeviceId]:
        return list(self._storage_ids)

    def eject_storage_device(self, device_id: UsbDeviceId) -> DeviceEjectResult:
        self.eject_calls.append(device_id.instance_id)
        if self.raise_on_eject is not None:
            raise self.raise_on_eject
        if self.next_eject_result is not None:
            return self.next_eject_result
        return DeviceEjectResult(
            success=False,
            attempted_instance_id=device_id.instance_id,
            config_ret=1,
        )


@pytest.fixture(scope="module")
def qapp() -> QtCore.QCoreApplication:
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtCore.QCoreApplication([])
    return app


class SignalCatcher:
    def __init__(self, signal: Any) -> None:
        self._signal = signal
        self.calls: list[tuple[Any, ...]] = []
        signal.connect(self._handler)

    def _handler(self, *args: Any) -> None:
        self.calls.append(args)

    def disconnect(self) -> None:
        self._signal.disconnect(self._handler)


def wait_until(condition: Callable[[], bool], *, timeout_ms: int = 2000) -> None:
    loop = QtCore.QEventLoop()

    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    poll = QtCore.QTimer()
    poll.setInterval(0)

    def check() -> None:
        if condition():
            loop.quit()

    poll.timeout.connect(check)
    poll.start()

    while timer.isActive() and not condition():
        loop.exec()

    poll.stop()
    assert condition(), "timed out waiting for condition"


def make_manager(
    app: QtCore.QCoreApplication,
) -> tuple[MainAreaStateManager, FakeBaseDeviceService, FakeStorageDeviceService]:
    base = FakeBaseDeviceService()
    storage = FakeStorageDeviceService(base)

    base.add_device("A", product="A")
    base.add_device("B", product="B")
    storage.add_storage("B")

    manager = MainAreaStateManager(app, base, storage)
    return manager, base, storage


class TestRefresh:
    def test_refresh_success_populates_devices_and_storages(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, _base, _storage = make_manager(qapp)

        state_changed = SignalCatcher(manager.stateChanged)
        try:
            manager.refresh()
            wait_until(
                lambda: (
                    isinstance(manager.state(), MainAreaState)
                    and not manager.state().is_scanning
                    and manager.state().last_operation == "refresh"
                    and manager.state().last_operation_error is None
                    and manager.state().refresh_error is None
                    and manager.state().device_count == 2
                    and len(manager.state().devices) == 2
                    and any(
                        isinstance(d, UsbStorageDeviceInfo) and d.base.id.instance_id == "B"
                        for d in manager.state().devices
                    )
                    and any(
                        isinstance(d, UsbBaseDeviceInfo) and d.id.instance_id == "A"
                        for d in manager.state().devices
                    )
                    and any(k.instance_id == "B" for k in manager.state().storages)
                )
            )

            assert any(
                isinstance(args[0], MainAreaState) and args[0].is_scanning
                for args in state_changed.calls
            )
        finally:
            state_changed.disconnect()

    def test_refresh_skips_storage_info_failures(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _base, storage = make_manager(qapp)
        storage.raise_on_get_info.add("B")

        manager.refresh()
        wait_until(
            lambda: (
                not manager.state().is_scanning
                and manager.state().last_operation == "refresh"
                and manager.state().last_operation_error is None
                and manager.state().device_count == 2
            )
        )

        # No storage entry should be present for B if storage info failed.
        assert not any(k.instance_id == "B" for k in manager.state().storages)

        # And devices should contain base info for B (not UsbStorageDeviceInfo).
        assert any(
            isinstance(d, UsbBaseDeviceInfo) and d.id.instance_id == "B"
            for d in manager.state().devices
        )

    def test_refresh_failure_sets_error(self, qapp: QtCore.QCoreApplication) -> None:
        manager, base, _storage = make_manager(qapp)
        base.raise_on_refresh = RuntimeError("boom")

        manager.refresh()
        wait_until(
            lambda: (
                not manager.state().is_scanning
                and manager.state().last_operation == "refresh"
                and manager.state().last_operation_error is not None
                and manager.state().refresh_error is not None
            )
        )

        assert isinstance(manager.state().last_operation_error, RuntimeError)


class TestEject:
    def test_eject_success_sets_last_eject_result_and_triggers_refresh(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, base, storage = make_manager(qapp)

        storage.next_eject_result = DeviceEjectResult(
            success=True,
            attempted_instance_id="B",
            config_ret=0,
        )

        manager.eject_storage_device(UsbDeviceId(instance_id="B"))

        # Wait until refresh triggered by successful eject completes.
        wait_until(
            lambda: (
                base.refresh_calls >= 1
                and not manager.state().is_scanning
                and manager.state().last_operation == "refresh"
                and manager.state().last_operation_error is None
                and manager.state().last_eject_result is not None
            )
        )

        eject_result = manager.state().last_eject_result
        assert eject_result is not None
        assert eject_result.attempted_instance_id == "B"
        assert storage.eject_calls == ["B"]

    def test_eject_failure_sets_error(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _base, storage = make_manager(qapp)
        storage.raise_on_eject = RuntimeError("eject failed")

        manager.eject_storage_device(UsbDeviceId(instance_id="B"))
        wait_until(
            lambda: (
                not manager.state().is_scanning
                and manager.state().last_operation == "eject"
                and manager.state().last_operation_error is not None
            )
        )

        assert manager.state().last_eject_result is None
        assert storage.eject_calls == ["B"]

    def test_eject_ignored_while_scanning(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _base, storage = make_manager(qapp)

        manager.refresh()
        wait_until(lambda: manager.state().is_scanning)

        manager.eject_storage_device(UsbDeviceId(instance_id="B"))
        assert storage.eject_calls == []
