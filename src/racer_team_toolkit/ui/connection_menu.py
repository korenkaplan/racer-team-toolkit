"""A live connection header inside the same application as the menu."""

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import Box, Frame

from racer_team_toolkit.ui.connection_monitor import ConnectionMonitor, ConnectionState
from racer_team_toolkit.ui.functions import create_menu


def connection_header(state: ConnectionState) -> FormattedText:
    parts = []
    if state.adb_error:
        parts.append(("fg:ansired", "● ADB unavailable"))
    elif state.android_names is None:
        parts.append(("fg:ansiyellow", "● Android: Checking…"))
    elif not state.android_names:
        parts.append(("fg:ansired", "● No Android devices"))
    else:
        parts.append(("fg:ansigreen bold", "   ".join(f"● {name}" for name in state.android_names)))
    parts.append(("", "   "))
    if state.ronen_connected is None:
        parts.append(("fg:ansiyellow", "● Ronen: Checking…"))
    elif state.ronen_connected:
        parts.append(("fg:ansigreen bold", "● Ronen"))
    else:
        parts.append(("fg:ansired", "● Ronen: Disconnected"))
    return FormattedText(parts)


def select_connected_menu(monitor: ConnectionMonitor, choices: list[str]) -> str | None:
    question = create_menu("Select a tool:", choices)
    application = question.application
    header = Window(
        FormattedTextControl(lambda: connection_header(monitor.snapshot())),
        wrap_lines=True,
    )
    panel = Frame(
        Box(header, padding=1, padding_left=2, padding_right=2),
        title="Racer Team Toolkit",
        style="fg:ansicyan",
        width=lambda: max(
            28,
            get_cwidth("".join(text for _, text in connection_header(monitor.snapshot()))) + 6,
        ),
    )
    application.layout.container = HSplit([panel, application.layout.container])
    monitor.set_notify(application.invalidate)
    try:
        return question.ask()
    finally:
        monitor.set_notify(None)
