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
from umanager.ui.states import MainAreaStateManager, OverviewState, OverviewStateManager


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

    def add_storage(self, instance_id: str) -> UsbStorageDeviceInfo:
        dev_id = UsbDeviceId(instance_id=instance_id)
        if instance_id not in {i.instance_id for i in self._storage_ids}:
            self._storage_ids.append(dev_id)
        base_info = self._base.get_base_device_info(dev_id)
        return UsbStorageDeviceInfo(base=base_info)

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
        if self.next_eject_result is None:
            return DeviceEjectResult(
                success=False,
                attempted_instance_id=device_id.instance_id,
                config_ret=1,
            )
        return self.next_eject_result


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
) -> tuple[OverviewStateManager, FakeBaseDeviceService, FakeStorageDeviceService]:
    base = FakeBaseDeviceService()
    storage = FakeStorageDeviceService(base)

    base.add_device("A", product="A")
    base.add_device("B", product="B")
    storage.add_storage("B")

    main_area = MainAreaStateManager(app, base, storage)
    manager = OverviewStateManager(app, main_area)
    return manager, base, storage


class TestRefresh:
    def test_refresh_success_sets_devices_and_clears_scanning(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, _base, _storage = make_manager(qapp)

        state_changed = SignalCatcher(manager.stateChanged)
        try:
            manager.refresh()
            wait_until(
                lambda: (
                    isinstance(manager.state(), OverviewState)
                    and not manager.state().is_scanning
                    and manager.state().device_count == 2
                    and len(manager.state().devices) == 2
                    and manager.state().last_operation == "refresh"
                    and manager.state().last_operation_error is None
                )
            )

            # Should have observed scanning=True at some point.
            assert any(
                isinstance(args[0], OverviewState) and args[0].is_scanning
                for args in state_changed.calls
            )
        finally:
            state_changed.disconnect()

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


class TestSelectionAndRequests:
    def test_set_selected_device_updates_state(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _base, _storage = make_manager(qapp)
        manager.refresh()
        wait_until(lambda: not manager.state().is_scanning and manager.state().device_count == 2)

        # Pick a storage device from loaded state.
        selected_storage = next(
            d for d in manager.state().devices if isinstance(d, UsbStorageDeviceInfo)
        )
        manager.set_selected_device(selected_storage.base, selected_storage)
        selection = manager.state().selected_device
        assert selection is not None
        base, storage = selection
        assert base.id.instance_id == "B"
        assert storage is not None

    def test_selection_is_cleared_after_refresh_completes(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, base, _storage = make_manager(qapp)

        # Select a device during the first refresh; selection should be cleared
        # when a completed refresh is observed.
        manager.refresh()
        wait_until(lambda: manager.state().is_scanning)

        base_info = base.get_base_device_info(UsbDeviceId(instance_id="B"))
        manager.set_selected_device(base_info, UsbStorageDeviceInfo(base=base_info))
        assert manager.state().selected_device is not None

        wait_until(
            lambda: (
                manager.state().last_operation == "refresh"
                and not manager.state().is_scanning
                and manager.state().selected_device is None
            )
        )

    def test_request_file_manager_emits_only_for_storage(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, _base, _storage = make_manager(qapp)
        manager.refresh()
        wait_until(lambda: not manager.state().is_scanning and manager.state().device_count == 2)

        requested = SignalCatcher(manager.fileManagerRequested)
        try:
            # Select base-only device (A)
            base_only = next(d for d in manager.state().devices if isinstance(d, UsbBaseDeviceInfo))
            manager.set_selected_device(base_only, None)
            manager.request_file_manager()
            assert requested.calls == []

            # Select storage device (B)
            storage_dev = next(
                d for d in manager.state().devices if isinstance(d, UsbStorageDeviceInfo)
            )
            manager.set_selected_device(storage_dev.base, storage_dev)
            manager.request_file_manager()
            wait_until(lambda: len(requested.calls) >= 1)
            base, storage = requested.calls[-1]
            assert base.id.instance_id == "B"
            assert storage is not None
        finally:
            requested.disconnect()


class TestEject:
    def test_request_eject_emits_and_sets_last_eject_result(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, _base, storage = make_manager(qapp)
        manager.refresh()
        wait_until(lambda: not manager.state().is_scanning and manager.state().device_count == 2)

        storage_dev = next(
            d for d in manager.state().devices if isinstance(d, UsbStorageDeviceInfo)
        )
        manager.set_selected_device(storage_dev.base, storage_dev)

        requested = SignalCatcher(manager.ejectRequested)
        try:
            storage.next_eject_result = DeviceEjectResult(
                success=False,
                attempted_instance_id=storage_dev.base.id.instance_id,
                config_ret=1,
            )

            manager.request_eject()
            wait_until(lambda: len(requested.calls) >= 1)

            # Wait for async completion.
            wait_until(
                lambda: (
                    manager.state().last_operation == "eject"
                    and manager.state().last_operation_error is None
                    and manager.state().last_eject_result is not None
                    and not manager.state().is_scanning
                )
            )

            eject_result = manager.state().last_eject_result
            assert eject_result is not None
            assert eject_result.attempted_instance_id == "B"
            assert storage.eject_calls == ["B"]
        finally:
            requested.disconnect()
