from threading import Event, Thread

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from racer_team_toolkit.ui import connection_menu
from racer_team_toolkit.ui.connection_monitor import ConnectionMonitor, ConnectionState
from racer_team_toolkit.ui.functions import create_menu


def test_slow_ssh_does_not_block_adb_or_initial_state():
    release_ssh = Event()
    adb_ready = Event()
    ssh_started = Event()

    def ssh():
        ssh_started.set()
        assert release_ssh.wait(2)
        return True

    monitor = ConnectionMonitor(adb_probe=lambda: ("Tablet",), ssh_probe=ssh)
    assert monitor.snapshot() == ConnectionState()
    monitor.set_notify(lambda: adb_ready.set() if monitor.snapshot().android_names else None)
    with monitor:
        try:
            assert adb_ready.wait(1)
            assert ssh_started.wait(1)
            assert monitor.snapshot().android_names == ("Tablet",)
            assert monitor.snapshot().ronen_connected is None
        finally:
            release_ssh.set()
    assert all(not thread.is_alive() for thread in monitor._threads)


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


def test_failed_adb_probe_recovers_without_printing(capsys):
    recovered = Event()
    seen_error = Event()
    calls = 0

    def adb():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("ADB unavailable")
        return ("Tablet",)

    monitor = ConnectionMonitor(adb_probe=adb, ssh_probe=lambda: False, adb_interval=0.01)

    def notify():
        if monitor.snapshot().adb_error:
            seen_error.set()
        elif monitor.snapshot().android_names:
            recovered.set()

    monitor.set_notify(notify)
    with monitor:
        assert seen_error.wait(1)
        assert recovered.wait(1)
    assert capsys.readouterr().out == ""


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
