"""One terminal renderer and one lifetime timer per operation target."""

from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic
from typing import TypeVar

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from racer_team_toolkit.multithreading.updates import run_with_updates

Result = TypeVar("Result")


@dataclass(frozen=True)
class OperationUpdate:
    key: str
    message: str
    state: str = "running"
    timestamp: float = field(default_factory=monotonic)


@dataclass
class OperationRow:
    component: str
    target: str
    message: str = "Waiting"
    state: str = "waiting"
    started: float | None = None
    finished: float | None = None
    history: list[str] = field(default_factory=list)


class OperationTable:
    def __init__(self, title: str, targets: list[tuple[str, str, str]]):
        self.title = title
        self.rows = {key: OperationRow(component, target) for key, component, target in targets}

    def update(self, event: OperationUpdate) -> None:
        row = self.rows[event.key]
        if row.finished is not None:
            return
        if row.started is None:
            row.started = event.timestamp
        row.message = event.message
        row.state = event.state
        if not row.history or row.history[-1] != event.message:
            row.history.append(event.message)
        if event.state in {"success", "warning", "failed", "skipped"}:
            row.finished = event.timestamp

    def render(self, now: float | None = None) -> Table:
        now = monotonic() if now is None else now
        table = Table(title=self.title, show_lines=True, expand=True)
        table.add_column("Component", no_wrap=True)
        table.add_column("Target", ratio=1)
        table.add_column("Status", ratio=3)
        table.add_column("Elapsed", no_wrap=True, justify="right")
        styles = {"success": "green", "failed": "red", "warning": "yellow", "skipped": "yellow"}
        for row in self.rows.values():
            seconds = (
                int(max(0, (row.finished if row.finished is not None else now) - row.started))
                if row.started is not None
                else 0
            )
            elapsed = f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"
            table.add_row(
                Text(row.component),
                Text(row.target),
                Text(row.message, style=styles.get(row.state, "cyan")),
                Text(elapsed),
            )
        return table


def run_with_operation_table(
    title: str,
    targets: list[tuple[str, str, str]],
    operation: Callable[[Callable[[OperationUpdate], None]], Result],
    console: Console,
) -> Result:
    """Workers enqueue events. Only the caller renders or prints diagnostics."""
    table = OperationTable(title, targets)
    # Redirected output gets one final snapshot, never repeated progress frames.
    if console.is_terminal:
        with Live(table.render(), console=console, auto_refresh=False) as live:
            result = run_with_updates(
                operation, table.update, lambda: live.update(table.render(), refresh=True)
            )
    else:
        result = run_with_updates(operation, table.update)
        console.print(table.render())
    for row in table.rows.values():
        if row.state == "failed":
            console.rule(Text(f"{row.component} — {row.target}: details"))
            for message in row.history:
                console.print(Text(message))
    return result


def apk_status_update(serial: str, message: str) -> OperationUpdate:
    """Only the install_devices final event ends a device's timer."""
    state = "running"
    if message.startswith("✓ Completed"):
        state = "warning" if "warnings" in message else "success"
    elif message == "✗ Failed":
        state = "failed"
    elif message.startswith("⚠ Skipped"):
        state = "skipped"
    return OperationUpdate(f"apk:{serial}", message.removesuffix("..."), state)
