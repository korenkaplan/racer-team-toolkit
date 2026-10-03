import io
from queue import Queue
from threading import Event, Thread

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from racer_team_toolkit.ui import connection_menu
from racer_team_toolkit.ui.connection_monitor import (
    ConnectionMonitor,
    ConnectionState,
    device_names,
    read_device_snapshot,
)
from racer_team_toolkit.ui.functions import create_menu


class TrackerStream:
    def __init__(self):
        self.chunks = Queue()
        self.buffer = b""
        self.ended = False

    def read(self, size):
        if not self.buffer and not self.ended:
            chunk = self.chunks.get(timeout=3)
            if chunk is None:
                self.ended = True
            else:
                self.buffer = chunk
        result, self.buffer = self.buffer[:size], self.buffer[size:]
        return result

    def close(self):
        pass


class FakeTracker:
    def __init__(self):
        self.stdout = TrackerStream()
        self.returncode = None
        self.terminated = Event()

    def send(self, payload):
        payload = payload.encode()
        self.stdout.chunks.put(f"{len(payload):04x}".encode() + payload)

    def finish(self):
        self.returncode = 0
        self.stdout.chunks.put(None)

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated.set()
        self.finish()

    def wait(self, timeout=None):
        return self.returncode


def test_state_changes_notify_but_identical_results_do_not():
    monitor = ConnectionMonitor()
    notifications = []
    monitor.set_notify(lambda: notifications.append(True))
    monitor._publish(android_names=("Tablet",), ronen_connected=True)
    monitor._publish(android_names=("Tablet",), ronen_connected=True)
    assert len(notifications) == 1
    monitor._publish(android_names=(), ronen_connected=False)
    assert len(notifications) == 2
    assert monitor.snapshot() == ConnectionState(android_names=(), ronen_connected=False)
    monitor.set_notify(None)
    monitor._publish(android_names=("ISR",))
    assert len(notifications) == 2


def test_live_redraw_keeps_keyboard_selection(monkeypatch):
    monitor = ConnectionMonitor()
    first_render = Event()
    changed_render = Event()
    errors = []
    with create_pipe_input() as pipe:
        with create_app_session(input=pipe, output=DummyOutput()):
            question = create_menu("Select a tool:", ["First", "Second"])

            def rendered(_):
                first_render.set()
                if monitor.snapshot().ronen_connected is True:
                    changed_render.set()

            question.application.after_render += rendered
            monkeypatch.setattr(connection_menu, "create_menu", lambda *args: question)

            def operate():
                try:
                    assert first_render.wait(2)
                    pipe.send_text("\x1b[B")
                    monitor._publish(android_names=("Tablet",), ronen_connected=True)
                    assert changed_render.wait(2)
                    pipe.send_text("\r")
                except BaseException as error:
                    errors.append(error)
                    pipe.send_text("\x03")

            operator = Thread(target=operate, daemon=True)
            operator.start()
            assert connection_menu.select_connected_menu(monitor, ["First", "Second"]) == "Second"
            operator.join(timeout=2)
            assert not errors
            assert monitor._notify is None


def test_header_shows_pending_connected_and_disconnected():
    def text(state):
        return "".join(fragment[1] for fragment in connection_menu.connection_header(state))

    assert "Checking" in text(ConnectionState())
    connected = text(ConnectionState(android_names=("Tablet",), ronen_connected=True))
    assert "Tablet" in connected and "Ronen" in connected
    disconnected = text(ConnectionState(android_names=(), ronen_connected=False))
    assert "No Android devices" in disconnected and "Disconnected" in disconnected


def test_frame_parser_handles_fragmented_empty_and_consecutive_snapshots():
    stream = TrackerStream()
    payload = b"ABC\tdevice model:SM-X820\n"
    framed = f"{len(payload):04x}".encode() + payload + b"0000"
    for byte in framed:
        stream.chunks.put(bytes([byte]))
    assert read_device_snapshot(stream) == payload.decode()
    assert read_device_snapshot(stream) == ""
    with pytest.raises(EOFError):
        read_device_snapshot(io.BytesIO(b"0005ab"))
    with pytest.raises(ValueError):
        read_device_snapshot(io.BytesIO(b"oops"))


def test_device_metadata_handles_ready_unauthorized_and_offline():
    assert device_names(
        "A\tdevice product:test model:SM-X820 transport_id:1\n"
        "B\tdevice model:RCPad\nC\tunauthorized\nD\toffline\n"
    ) == ("Tablet", "ISR Controller", "C (unauthorized)", "D (offline)")
    assert device_names("") == ()


def test_tracker_idle_uses_one_process_and_updates_on_events():
    tracker = FakeTracker()
    connected = Event()
    disconnected = Event()
    starts = []

    def factory():
        starts.append(True)
        return tracker

    monitor = ConnectionMonitor(tracker_factory=factory)

    def changed():
        if monitor.snapshot().android_names:
            connected.set()
        elif monitor.snapshot().android_names == ():
            disconnected.set()

    monitor.set_notify(changed)
    with monitor:
        tracker.send("A\tdevice model:SM-X820\n")
        assert connected.wait(1)
        tracker.send("")
        assert disconnected.wait(1)
        assert len(starts) == 1
    assert tracker.terminated.is_set()
    assert all(not thread.is_alive() for thread in monitor._threads)


def test_tracker_restarts_on_eof_and_recovers_quietly(capsys):
    failed = FakeTracker()
    failed.finish()
    healthy = FakeTracker()
    healthy.send("A\tdevice model:SM-X820\n")
    trackers = iter([failed, healthy])
    unavailable = Event()
    recovered = Event()
    monitor = ConnectionMonitor(tracker_factory=lambda: next(trackers), restart_delay=0.01)

    def changed():
        if monitor.snapshot().adb_error:
            unavailable.set()
        elif monitor.snapshot().android_names:
            recovered.set()

    monitor.set_notify(changed)
    with monitor:
        assert unavailable.wait(1)
        assert recovered.wait(1)
    assert capsys.readouterr().out == ""
    assert healthy.terminated.is_set()


def test_ssh_pauses_outside_menu_and_resumes_immediately():
    tracker = FakeTracker()
    checked = Event()
    calls = []

    def ssh():
        calls.append(True)
        checked.set()
        return True

    monitor = ConnectionMonitor(tracker_factory=lambda: tracker, ssh_probe=ssh, ssh_interval=0.05)
    with monitor:
        assert not checked.wait(0.08)
        monitor.set_menu_active(True)
        assert checked.wait(1)
        monitor.set_menu_active(False)
        checked.clear()
        assert not checked.wait(0.15)
        assert len(calls) == 1
        monitor.set_menu_active(True)
        assert checked.wait(1)
        monitor.set_menu_active(False)
    assert all(not thread.is_alive() for thread in monitor._threads)


def test_slow_ssh_does_not_block_android_and_discards_result_after_menu_exit():
    tracker = FakeTracker()
    started = Event()
    release = Event()
    adb_ready = Event()

    def ssh():
        started.set()
        assert release.wait(2)
        return True

    monitor = ConnectionMonitor(tracker_factory=lambda: tracker, ssh_probe=ssh)
    monitor.set_notify(lambda: adb_ready.set() if monitor.snapshot().android_names else None)
    with monitor:
        try:
            monitor.set_menu_active(True)
            assert started.wait(1)
            tracker.send("A\tdevice model:SM-X820\n")
            assert adb_ready.wait(1)
            assert monitor.snapshot().ronen_connected is None
            monitor.set_menu_active(False)
        finally:
            release.set()
    assert monitor.snapshot().ronen_connected is None
    assert all(not thread.is_alive() for thread in monitor._threads)


def test_real_tracker_subprocess_is_terminated_on_exit(monkeypatch):
    import subprocess
    import sys

    from racer_team_toolkit.ui import connection_monitor

    real_popen = subprocess.Popen
    children = []
    received = Event()
    monkeypatch.setattr(connection_monitor, "get_adb_executable", lambda: "test-adb")

    def spawn(command, **kwargs):
        assert command == ["test-adb", "track-devices", "-l"]
        child = real_popen(
            [
                sys.executable,
                "-u",
                "-c",
                "import sys,time; sys.stdout.buffer.write(b'0000'); "
                "sys.stdout.buffer.flush(); time.sleep(30)",
            ],
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr(connection_monitor.subprocess, "Popen", spawn)
    monitor = ConnectionMonitor()
    monitor.set_notify(received.set)
    with monitor:
        assert received.wait(2)
        assert monitor.snapshot().android_names == ()
        assert children[0].poll() is None
    assert children[0].poll() is not None
    assert all(not thread.is_alive() for thread in monitor._threads)
