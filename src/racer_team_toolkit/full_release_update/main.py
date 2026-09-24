"""Interactive full release update flow."""

from racer_team_toolkit.adb.functions import (
    get_connected_android_devices,
)
from racer_team_toolkit.full_release_update.functions import (
    execute_release_update,
    prepare_release_update,
)
from racer_team_toolkit.ui.functions import (
    console,
    pause,
    print_error,
    select_menu,
)


def main() -> None:
    """Run the full release update flow."""

    connected_devices = get_connected_android_devices()

    if not connected_devices:
        print_error("No devices are connected. Please connect a device and try again.")
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
