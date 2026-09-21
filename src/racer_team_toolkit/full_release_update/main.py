"""Interactive full release update flow."""

from racer_team_toolkit.adb.functions import (
    get_connected_android_devices,
)
from racer_team_toolkit.full_release_update.functions import (
    execute_release_update,
    prepare_release_update,
)
from racer_team_toolkit.full_release_update.online_release import (
    is_internet_available,
)
from racer_team_toolkit.ui.functions import (
    console,
    pause,
    print_error,
    print_header,
    print_info,
    run_with_spinner,
    select_menu,
)


def main() -> None:
    """Run the full release update flow."""

    print_header("Full Release Update")

    internet_available = run_with_spinner(
        "Checking internet connection...",
        is_internet_available,
    )

    if internet_available:
        release_source = select_menu(
            "Select release source:",
            [
                "Online Release",
                "Local Release",
            ],
        )

    else:
        print_info("No internet connection detected. Using local release files.")
        release_source = "Local Release"

    connected_devices = get_connected_android_devices()

    if not connected_devices:
        print_error("No devices are connected. Please connect a device and try again.")
        pause("Press Enter to return to the main menu...")
        return

    if release_source == "Online Release":
        console.print()
        console.print("[yellow]Online release flow is not implemented yet.[/yellow]")
        pause("Press Enter to return to the main menu...")
        return

    plan = prepare_release_update(
        connected_devices,
    )

    if plan is None:
        console.print("[yellow]Full release update cancelled.[/yellow]")
        return

    confirmation = select_menu(
        "Run this full release update?",
        [
            "Yes",
            "Cancel",
        ],
    )

    if confirmation != "Yes":
        console.print("[yellow]Full release update cancelled.[/yellow]")
        return

    execute_release_update(
        plan,
    )

    console.print()
    console.print("[bold]Full release update finished.[/bold]")

    pause("Press Enter to return to the main menu...")


if __name__ == "__main__":
    main()
