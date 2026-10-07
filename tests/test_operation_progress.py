"""Persistent timers, ordered rows, and quiet background JAR operations."""

from io import StringIO
from threading import get_ident
from unittest.mock import MagicMock, Mock

import pytest
from rich.console import Console

from racer_team_toolkit.jar_management import functions as jar
from racer_team_toolkit.ssh import functions as ssh_functions
from racer_team_toolkit.ui.operation_progress import (
    OperationTable,
    OperationUpdate,
    apk_status_update,
    run_with_operation_table,
)


def test_timer_spans_steps_and_freezes_only_on_final_result():
    table = OperationTable("Updates", [("apk:T", "APK", "Tablet"), ("jar", "JAR", "Ronen")])
    table.update(OperationUpdate("apk:T", "Checking", timestamp=10))
    table.update(OperationUpdate("jar", "Uploading", timestamp=11))
    table.update(OperationUpdate("apk:T", "Installing", timestamp=13))
    table.update(OperationUpdate("apk:T", "✓ Permissions granted", timestamp=16))
    assert table.rows["apk:T"].started == 10
    assert table.rows["apk:T"].finished is None
    table.update(OperationUpdate("apk:T", "Completed", "success", timestamp=19))
    table.update(OperationUpdate("apk:T", "Stale event", timestamp=22))
    stream = StringIO()
    Console(file=stream, width=90).print(table.render(now=30))
    assert "00:00:09" in stream.getvalue()
    assert "00:00:19" in stream.getvalue()
    assert list(table.rows) == ["apk:T", "jar"]
    assert table.rows["apk:T"].message == "Completed"
    assert apk_status_update("T", "✓ Permissions granted").state == "running"
    assert apk_status_update("T", "✓ Completed with warnings").state == "warning"


@pytest.mark.parametrize("terminal", [False, True])
def test_only_calling_thread_renders_and_non_tty_has_one_snapshot(monkeypatch, terminal):
    caller = get_ident()
    stream = StringIO()
    console = Console(file=stream, force_terminal=terminal, width=85)
    original = console.print

    def checked_print(*args, **kwargs):
        assert get_ident() == caller
        return original(*args, **kwargs)

    monkeypatch.setattr(console, "print", checked_print)

    def operation(report):
        assert get_ident() != caller
        report(OperationUpdate("jar", "Upload 50%"))
        report(OperationUpdate("apk:T", "Installing"))
        report(OperationUpdate("jar", "Completed", "success"))
        report(OperationUpdate("apk:T", "Completed", "success"))
        return 42

    assert (
        run_with_operation_table(
            "Release Progress",
            [("apk:T", "APK", "Tablet"), ("jar", "JAR", "Ronen")],
            operation,
            console,
        )
        == 42
    )
    if not terminal:
        assert stream.getvalue().count("Release Progress") == 1
        assert stream.getvalue().index("Tablet") < stream.getvalue().index("Ronen")
        assert "Upload 50%" not in stream.getvalue()


@pytest.mark.parametrize("failure", [None, "stop", "screen", "upload", "java", "verify"])
def test_jar_callback_mode_has_no_console_output(tmp_path, monkeypatch, capsys, failure):
    path = tmp_path / "racer-groundlord.jar"
    path.write_bytes(b"fixture")
    messages = []
    ssh = MagicMock()
    monkeypatch.setattr(jar, "is_ssh_server_reachable", lambda: True)
    monkeypatch.setattr(jar, "connect_to_server", lambda **_: ssh)
    monkeypatch.setattr(jar, "SSH_PASSWORD", "test-only")

    def command(_, command):
        if command == "killall screen":
            return (2, "", "stop denied") if failure == "stop" else (0, "", "")
        if command == "screen -ls":
            return (
                (0, "There is a screen on", "")
                if failure == "screen"
                else (1, "No sockets found", "")
            )
        return (1, "", "verify denied") if failure == "verify" else (0, "racer-groundlord.jar", "")

    monkeypatch.setattr(jar, "run_remote_command", command)
    sftp = ssh.open_sftp.return_value.__enter__.return_value = Mock()

    def put(*_, callback):
        if failure == "upload":
            raise OSError("upload denied")
        callback(1, 2)
        callback(2, 2)

    sftp.put.side_effect = put
    stdin, stdout, stderr = Mock(), Mock(), Mock()
    stdout.channel.recv_exit_status.return_value = 1 if failure == "java" else 0
    stdout.read.return_value = b"startup output"
    stderr.read.return_value = b"java denied" if failure == "java" else b""
    ssh.exec_command.return_value = stdin, stdout, stderr
    assert jar.upload_selected_jar(path, status_callback=messages.append) == (failure is None)
    assert capsys.readouterr().out == ""
    assert messages
    ssh.close.assert_called_once()
    if failure is None:
        assert "Uploading JAR: 50%" in messages
        assert "Uploading JAR: 100%" in messages
        assert messages[-1] == "✓ Racer Groundlord is running"
    else:
        assert any("denied" in msg or "still running" in msg for msg in messages)


def test_ssh_error_is_sent_to_callback(capsys):
    messages = []
    assert ssh_functions.connect_to_server(password=None, status_callback=messages.append) is None
    assert "SSH_PASSWORD" in messages[0]
    assert capsys.readouterr().out == ""
