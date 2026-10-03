"""Event-driven Android tracking and menu-only SSH checks."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Condition, Event, Lock, Thread
from time import monotonic
from typing import BinaryIO

from racer_team_toolkit.adb.device_detection import DeviceType, classify_device
from racer_team_toolkit.adb.functions import get_adb_executable
from racer_team_toolkit.config import DEVICE_TYPE_CONFIGS
from racer_team_toolkit.ssh.functions import is_ssh_server_reachable


@dataclass(frozen=True)
class ConnectionState:
    android_names: tuple[str, ...] | None = None
    adb_error: bool = False
    ronen_connected: bool | None = None


def read_device_snapshot(stream: BinaryIO) -> str:
    """Read one ADB track-devices frame (four hex bytes, then payload)."""

    def read_exact(size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = stream.read(size - len(data))
            if not chunk:
                raise EOFError("ADB tracker closed its output")
            data.extend(chunk)
        return bytes(data)

    header = read_exact(4)
    if any(byte not in b"0123456789abcdefABCDEF" for byte in header):
        raise ValueError("Invalid ADB tracker frame")
    return read_exact(int(header, 16)).decode("utf-8", errors="replace")


def device_names(snapshot: str) -> tuple[str, ...]:
    """Resolve long-format model metadata without issuing shell commands."""

    names = []
    for line in sorted(snapshot.splitlines()):
        fields = line.split()
        if len(fields) < 2:
            continue
        serial, status = fields[:2]
        if status != "device":
            # Report connected but unusable devices without treating them as ready.
            if status in {"offline", "unauthorized"}:
                names.append(f"{serial} ({status})")
            continue
        model = next((field[6:] for field in fields[2:] if field.startswith("model:")), "")
        model = model.replace("_", " ")
        device_type = classify_device(model)
        names.append(
            DEVICE_TYPE_CONFIGS[device_type.value].name
            if device_type != DeviceType.UNKNOWN
            else model or serial
        )
    return tuple(names)


class ConnectionMonitor:
    """Cache tracker events; workers never print or modify the menu layout."""

    def __init__(
        self, *, tracker_factory=None, ssh_probe=None, restart_delay=1.0, ssh_interval=5.0
    ):
        self._stop = Event()
        self._lock = Lock()
        self._state = ConnectionState()
        self._notify: Callable[[], None] | None = None
        self._tracker_factory = tracker_factory or self._start_tracker
        self._tracker_lock = Lock()
        self._tracker = None
        self._menu_condition = Condition()
        self._menu_active = False
        self._menu_generation = 0
        self._ssh_probe = ssh_probe or (lambda: is_ssh_server_reachable(timeout=2.0))
        self._threads = [
            Thread(target=self._track_android, args=(restart_delay,), daemon=True),
            Thread(target=self._poll_ssh, args=(ssh_interval,), daemon=True),
        ]

    @staticmethod
    def _start_tracker():
        return subprocess.Popen(
            [get_adb_executable(), "track-devices", "-l"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def snapshot(self) -> ConnectionState:
        with self._lock:
            return self._state

    def set_notify(self, callback: Callable[[], None] | None) -> None:
        with self._lock:
            self._notify = callback

    def set_menu_active(self, active: bool) -> None:
        """Wake SSH monitoring on entry; prevent new checks after leaving."""
        with self._menu_condition:
            if active != self._menu_active:
                self._menu_active = active
                self._menu_generation += 1
                self._menu_condition.notify_all()

    def _publish(self, **changes) -> None:
        with self._lock:
            updated = replace(self._state, **changes)
            if updated == self._state:
                return
            self._state = updated
            notify = self._notify
        if notify is not None:
            notify()  # prompt_toolkit.invalidate is thread-safe.

    @staticmethod
    def _terminate_tracker(process) -> None:
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.5)
        else:
            process.wait()

    def _track_android(self, restart_delay):
        while not self._stop.is_set():
            process = None
            try:
                # Register atomically so shutdown cannot miss a newly spawned child.
                with self._tracker_lock:
                    if self._stop.is_set():
                        return
                    process = self._tracker_factory()
                    self._tracker = process
                if process.stdout is None:
                    raise RuntimeError("ADB tracker has no output stream")
                while not self._stop.is_set():
                    snapshot = read_device_snapshot(process.stdout)
                    self._publish(android_names=device_names(snapshot), adb_error=False)
            except (OSError, EOFError, ValueError, RuntimeError):
                if not self._stop.is_set():
                    self._publish(android_names=(), adb_error=True)
            finally:
                if process is not None:
                    with self._tracker_lock:
                        self._terminate_tracker(process)
                        if self._tracker is process:
                            self._tracker = None
                    if process.stdout is not None:
                        process.stdout.close()
            # Restart only after EOF/error; a healthy stream blocks awaiting events.
            if self._stop.wait(restart_delay):
                break

    def _poll_ssh(self, interval):
        next_check = 0.0
        generation = -1
        while not self._stop.is_set():
            with self._menu_condition:
                while not self._stop.is_set():
                    if not self._menu_active:
                        self._menu_condition.wait()
                        continue
                    if generation != self._menu_generation:
                        generation = self._menu_generation
                        next_check = 0.0
                    remaining = next_check - monotonic()
                    if remaining <= 0:
                        break
                    self._menu_condition.wait(timeout=remaining)
                if self._stop.is_set():
                    return
            # Never hold a UI lock across network I/O. One in-flight probe may
            # finish after menu exit, but no new probes start while paused.
            try:
                connected = bool(self._ssh_probe())
            except Exception:
                connected = False
            with self._menu_condition:
                if self._menu_active and generation == self._menu_generation:
                    self._publish(ronen_connected=connected)
            next_check = monotonic() + interval

    def __enter__(self):
        for thread in self._threads:
            thread.start()
        return self

    def __exit__(self, *_):
        self.set_notify(None)
        self._stop.set()
        with self._menu_condition:
            self._menu_condition.notify_all()
        with self._tracker_lock:
            if self._tracker is not None:
                self._terminate_tracker(self._tracker)
        for thread in self._threads:
            thread.join(timeout=2.5)
