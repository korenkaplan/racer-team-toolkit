"""Quiet background connection checks for the interactive main menu."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Event, Lock, Thread

from racer_team_toolkit.adb.device_detection import DeviceType, classify_device
from racer_team_toolkit.adb.functions import get_adb_executable
from racer_team_toolkit.config import DEVICE_TYPE_CONFIGS
from racer_team_toolkit.ssh.functions import is_ssh_server_reachable


@dataclass(frozen=True)
class ConnectionState:
    android_names: tuple[str, ...] | None = None
    adb_error: bool = False
    ronen_connected: bool | None = None


class ConnectionMonitor:
    """Keep cached state; workers never print or modify the menu layout."""

    def __init__(self, *, adb_probe=None, ssh_probe=None, adb_interval=1.0, ssh_interval=3.0):
        self._stop = Event()
        self._lock = Lock()
        self._state = ConnectionState()
        self._notify: Callable[[], None] | None = None
        self._models: dict[str, str] = {}
        self._adb_probe = adb_probe or self._check_android
        self._ssh_probe = ssh_probe or (lambda: is_ssh_server_reachable(timeout=2.0))
        self._threads = [
            Thread(target=self._poll_adb, args=(adb_interval,), daemon=True),
            Thread(target=self._poll_ssh, args=(ssh_interval,), daemon=True),
        ]

    def snapshot(self) -> ConnectionState:
        with self._lock:
            return self._state

    def set_notify(self, callback: Callable[[], None] | None) -> None:
        with self._lock:
            self._notify = callback

    def _publish(self, **changes) -> None:
        with self._lock:
            updated = replace(self._state, **changes)
            if updated == self._state:
                return
            self._state = updated
            notify = self._notify
        if notify is not None:
            notify()  # prompt_toolkit.invalidate is thread-safe.

    def _check_android(self) -> tuple[str, ...]:
        executable = get_adb_executable()

        def run(*arguments):
            return subprocess.run(
                [executable, *arguments],
                capture_output=True,
                text=True,
                check=True,
                timeout=2.0,
            ).stdout

        serials = sorted(
            fields[0]
            for line in run("devices").splitlines()
            if len(fields := line.split()) == 2 and fields[1] == "device"
        )
        self._models = {serial: name for serial, name in self._models.items() if serial in serials}
        names = []
        for serial in serials:
            if self._stop.is_set():
                break
            if serial not in self._models:
                model = run("-s", serial, "shell", "getprop", "ro.product.model").strip()
                device_type = classify_device(model)
                self._models[serial] = (
                    DEVICE_TYPE_CONFIGS[device_type.value].name
                    if device_type != DeviceType.UNKNOWN
                    else model or "Unknown Android"
                )
            names.append(self._models[serial])
        return tuple(names)

    def _poll_adb(self, interval):
        while not self._stop.is_set():
            try:
                self._publish(android_names=self._adb_probe(), adb_error=False)
            except Exception:
                self._publish(android_names=(), adb_error=True)
            if self._stop.wait(interval):
                break

    def _poll_ssh(self, interval):
        while not self._stop.is_set():
            try:
                connected = bool(self._ssh_probe())
            except Exception:
                connected = False
            self._publish(ronen_connected=connected)
            if self._stop.wait(interval):
                break

    def __enter__(self):
        for thread in self._threads:
            thread.start()
        return self

    def __exit__(self, *_):
        self.set_notify(None)
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2.5)
