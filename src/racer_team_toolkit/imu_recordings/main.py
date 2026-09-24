"""Interactive IMU recordings extraction flow."""

from racer_team_toolkit.imu_recordings.config import IMU_REMOTE_DIRECTORY
from racer_team_toolkit.imu_recordings.functions import (
    choose_imu_recordings,
    clear_imu_csv_files,
    copy_imu_recordings,
    get_imu_recordings,
    get_local_imu_directory,
)
from racer_team_toolkit.ssh.functions import (
    connect_to_server,
    is_ssh_server_reachable,
)
from racer_team_toolkit.ui.functions import (
    console,
    pause,
    print_error,
    print_header,
    run_with_spinner,
    select_menu,
)


def extract_recordings(ssh) -> None:
    """Select and copy IMU recordings from the server."""

    recordings = run_with_spinner(
        "Loading IMU recordings...",
        get_imu_recordings,
        ssh,
    )

    if not recordings:
        console.print("[yellow]No IMU recordings found.[/yellow]")
        return

    selected_recordings = choose_imu_recordings(
        recordings,
    )

    if not selected_recordings:
        console.print("[yellow]No recordings selected.[/yellow]")
        return

    destination = get_local_imu_directory()

    copied_files = copy_imu_recordings(
        ssh,
        selected_recordings,
        destination,
    )

    console.print()
    console.rule("[bold]IMU Extraction Results[/bold]")
    console.print()

    console.print(f"Selected: {len(selected_recordings)}")
    console.print(f"Copied:   {len(copied_files)}")
    console.print(f"Failed:   {len(selected_recordings) - len(copied_files)}")

    console.print()
    console.print(f"Destination: [bold]{destination}[/bold]")


def clear_recordings(ssh) -> None:
    """Confirm and delete all CSV files from the remote IMU directory."""

    recordings = run_with_spinner(
        "Checking IMU CSV files...",
        get_imu_recordings,
        ssh,
    )

    csv_count = len(recordings)

    if csv_count == 0:
        console.print("[yellow]No IMU CSV files found.[/yellow]")
        return

    console.print(
        f"[yellow]This will permanently delete {csv_count} CSV file(s) from "
        f"{IMU_REMOTE_DIRECTORY}.[/yellow]"
    )

    choice = select_menu(
        "Clear all IMU CSV files?",
        [
            "Yes, delete all CSV files",
            "Cancel",
        ],
    )

    if choice != "Yes, delete all CSV files":
        console.print("[yellow]Clear operation cancelled.[/yellow]")
        return

    deleted_count, failures = run_with_spinner(
        "Deleting IMU CSV files...",
        clear_imu_csv_files,
        ssh,
    )

    console.print()
    console.rule("[bold]IMU Cleanup Results[/bold]")
    console.print(f"Deleted: {deleted_count}")
    console.print(f"Failed:  {len(failures)}")

    for failure in failures:
        console.print(f"[red]✗ {failure}[/red]")


def main() -> None:
    """Run the IMU recordings extraction flow."""

    print_header("Extract IMU Recordings")

    server_reachable = run_with_spinner(
        "Checking IMU server connection...",
        is_ssh_server_reachable,
    )

    if not server_reachable:
        print_error("IMU server is not reachable.")
        pause()
        return

    console.print("[green]✓ IMU server is reachable[/green]")

    ssh = run_with_spinner(
        "Connecting to IMU server...",
        connect_to_server,
    )

    if ssh is None:
        print_error("Could not connect to IMU server.")
        pause()
        return

    console.print("[green]✓ Connected to IMU server[/green]")

    try:
        while True:
            choice = select_menu(
                "Select IMU recordings action:",
                [
                    "Extract IMU Recordings",
                    "Clear All CSV Files",
                    "Return to Main Menu",
                ],
            )

            if choice == "Extract IMU Recordings":
                extract_recordings(ssh)

            elif choice == "Clear All CSV Files":
                clear_recordings(ssh)

            else:
                break

    finally:
        ssh.close()

    pause("Press Enter to return to the main menu...")


if __name__ == "__main__":
    main()
