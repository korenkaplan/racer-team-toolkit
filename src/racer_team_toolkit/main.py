from racer_team_toolkit.apk_installer.main import main as run_apk_installer_main
from racer_team_toolkit.config import TOOL_MENU_CHOICES
from racer_team_toolkit.full_release_update.main import main as run_full_release_update_main
from racer_team_toolkit.jar_management.main import main as run_ronen_operations_main
from racer_team_toolkit.quick_reset.main import main as run_quick_reset_main
from racer_team_toolkit.reff_extractor.main import main as run_reff_and_videos_extractor_main
from racer_team_toolkit.ui.connection_menu import select_connected_menu
from racer_team_toolkit.ui.connection_monitor import ConnectionMonitor


def run_menu(monitor: ConnectionMonitor) -> None:
    """Run the Racer Team Toolkit main menu."""
    while True:
        choice = select_connected_menu(monitor, TOOL_MENU_CHOICES)

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


def main() -> None:
    with ConnectionMonitor() as monitor:
        run_menu(monitor)


if __name__ == "__main__":
    main()
