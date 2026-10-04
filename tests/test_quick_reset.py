"""Concurrent reset completion, failure isolation, and UI event delivery."""

from dataclasses import replace
from io import StringIO
from subprocess import CompletedProcess
from threading import Barrier, Event, get_ident

import pytest
from rich.console import Console

from racer_team_toolkit.multithreading.updates import run_with_updates
from racer_team_toolkit.quick_reset import functions as reset
from tests.test_apk_installer import make_device


def test_reset_workers_overlap_wait_and_isolate_failures(monkeypatch):
    devices = [replace(make_device(), serial=str(i)) for i in range(3)]
    rendezvous = Barrier(3, timeout=3)
    calls = {d.serial: [] for d in devices}
    finished = set()
    monkeypatch.setattr(reset, "REFF_REMOTE_PATHS", ["/reff"])
    monkeypatch.setattr(reset, "VIDEO_REMOTE_PATHS", ["/videos"])

    def delete(device, path):
        calls[device.serial].append(path)
        if path == "/reff":
            rendezvous.wait()  # Fails if devices are processed sequentially.
            if device.serial == "0":
                raise OSError("device disconnected")
        else:
            finished.add(device.serial)
        return device.serial != "1"

    monkeypatch.setattr(reset, "reset_remote_folder", delete)
    updates = []
    results = reset.reset_devices(
        devices,
        {d.serial: {"reff", "videos"} for d in devices},
        status_callback=updates.append,
    )
    assert finished == {"0", "1", "2"}  # All joined before return.
    assert [r.device.serial for r in results] == ["0", "1", "2"]
    assert [r.succeeded for r in results] == [False, False, True]
    assert all(paths == ["/reff", "/videos"] for paths in calls.values())
    for serial in calls:
        events = [event for event in updates if event.serial == serial]
        assert events[-1].completed == events[-1].total == 2
        assert events[-1].status == ("Done" if serial == "2" else "Failed")
    assert "device disconnected" in results[0].errors[0]


def test_only_selected_folders_and_devices_are_reset(monkeypatch):
    devices = [make_device(), replace(make_device(), serial="skip")]
    monkeypatch.setattr(reset, "VIDEO_REMOTE_PATHS", ["/videos", "/videos"])
    calls = []
    monkeypatch.setattr(
        reset, "reset_remote_folder", lambda d, p: calls.append((d.serial, p)) or True
    )
    results = reset.reset_devices(devices, {devices[0].serial: {"videos"}})
    assert calls == [(devices[0].serial, "/videos")]
    assert len(results) == 1
    assert reset.reset_devices(devices, {}) == []


def test_adb_failure_is_not_reported_as_missing_folder(monkeypatch):
    monkeypatch.setattr(reset, "run_adb_command", lambda args: CompletedProcess(args, 1))
    assert not reset.reset_remote_folder(make_device(), "/sdcard/Records")


@pytest.mark.parametrize("raises", [False, True])
def test_updates_delivered_on_caller_thread_before_return_or_error(raises):
    caller = get_ident()
    received = []
    delivered = Event()

    def operation(report):
        assert get_ident() != caller
        report("running")
        assert delivered.wait(3), "Caller must handle updates while batch runs"
        report("final")
        if raises:
            raise ValueError("batch failed")
        return 42

    def on_update(update):
        assert get_ident() == caller
        received.append(update)
        delivered.set()

    if raises:
        with pytest.raises(ValueError, match="batch failed"):
            run_with_updates(operation, on_update)
    else:
        assert run_with_updates(operation, on_update) == 42
    assert received == ["running", "final"]


def test_cli_table_finishes_with_failure_and_skipped_folder(monkeypatch):
    device = make_device()
    stream = StringIO()
    monkeypatch.setattr(reset, "console", Console(file=stream, width=140))
    monkeypatch.setattr(reset, "REFF_REMOTE_PATHS", ["/reff"])
    monkeypatch.setattr(reset, "reset_remote_folder", lambda *_: False)
    assert not reset.apply_reset_plan([device], {device.serial: {"reff"}})
    output = stream.getvalue()
    assert "Folder Reset Status" in output
    assert "Failed" in output and "1/1" in output
    assert "Screen Videos" in output
    assert "/reff: Reset command failed" in output
