"""Interactive full release update flow."""

from racer_team_toolkit.adb.functions import get_connected_android_devices
from racer_team_toolkit.full_release_update.functions import (
    build_release_update_plan,
    choose_release_folder,
    get_release_folders,
    print_release_update_plan,
    resolve_missing_apks,
    resolve_missing_jar,
)
from racer_team_toolkit.ui.functions import (
    console,
    pause,
    print_error,
    print_header,
    select_menu,
)


def main() -> None:
    """Run the full release update flow."""

    print_header("Full Release Update")

    connected_devices = get_connected_android_devices()

    if not connected_devices:
        print_error("No devices are connected. Please connect a device and try again.")
        pause("Press Enter to return to the main menu...")
        return

    release_folders = get_release_folders()

    if not release_folders:
        print_error("No release folders containing APK or JAR files were found in Downloads.")
        pause("Press Enter to return to the main menu...")
        return

    release_folder = choose_release_folder(
        release_folders,
    )

    plan = build_release_update_plan(
        release_folder,
        connected_devices,
    )

    console.print()
    console.print(f"Selected release folder: [bold]{release_folder}[/bold]")

    print_release_update_plan(
        plan,
    )

    if not resolve_missing_apks(
        plan,
    ):
        console.print("[yellow]Full release update cancelled.[/yellow]")
        return

    if not resolve_missing_jar(
        plan,
    ):
        console.print("[yellow]Full release update cancelled.[/yellow]")
        return

    console.print()
    console.print("[bold]Final update plan:[/bold]")

    print_release_update_plan(
        plan,
    )

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

    console.print()
    console.print("[green]Update approved.[/green]")


if __name__ == "__main__":
    main()
