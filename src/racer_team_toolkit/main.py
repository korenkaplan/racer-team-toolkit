from rich.panel import Panel
from rich.text import Text

from racer_team_toolkit.adb.functions import get_connected_android_devices
from racer_team_toolkit.apk_installer.main import main as run_apk_installer_main
from racer_team_toolkit.config import TOOL_MENU_CHOICES, AndroidDevice
from racer_team_toolkit.full_release_update.main import (
    main as run_full_release_update_main,
)
from racer_team_toolkit.jar_management.main import main as run_ronen_operations_main
from racer_team_toolkit.quick_reset.main import main as run_quick_reset_main
from racer_team_toolkit.reff_extractor.main import (
    main as run_reff_and_videos_extractor_main,
)
from racer_team_toolkit.ssh.functions import is_ssh_server_reachable
from racer_team_toolkit.ui.functions import (
    console,
    select_menu,
)


def print_connected_devices_in_header() -> None:
    connected_devices: list[AndroidDevice] = get_connected_android_devices()
    ronen_connected = is_ssh_server_reachable()

    devices_text = Text()

    for index, device in enumerate(connected_devices):
        if index > 0:
            devices_text.append("   ")

        devices_text.append("● ", style="green")
        devices_text.append(device.name, style="bold white")

    if ronen_connected:
        if connected_devices:
            devices_text.append("   ")

        devices_text.append("● ", style="green")
        devices_text.append("Ronen", style="bold white")

    if len(connected_devices) == 0:
        devices_text.append("● ", style="red")
        devices_text.append("No devices connected", style="bold red")

    panel = Panel.fit(
        devices_text,
        title="Racer Team Toolkit",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)


def main() -> None:
    """Run the Racer Team Toolkit main menu."""
    while True:
        print_connected_devices_in_header()

        choice = select_menu(
            "Select a tool:",
            TOOL_MENU_CHOICES,
        )

        if choice == TOOL_MENU_CHOICES[0]:
            run_full_release_update_main()

        elif choice == TOOL_MENU_CHOICES[1]:
            run_reff_and_videos_extractor_main()

        elif choice == TOOL_MENU_CHOICES[2]:
            run_apk_installer_main()

        elif choice == TOOL_MENU_CHOICES[3]:
            run_ronen_operations_main()

        elif choice == TOOL_MENU_CHOICES[4]:
            run_quick_reset_main()

        elif choice == TOOL_MENU_CHOICES[5] or choice is None:
            break


if __name__ == "__main__":
    main()
