"""Interactive IMU recordings extraction flow."""

from racer_team_toolkit.imu_recordings.functions import (
    choose_imu_recordings,
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
)


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
        recordings = run_with_spinner(
            "Loading IMU recordings...",
            get_imu_recordings,
            ssh,
        )

        if not recordings:
            console.print("[yellow]No IMU recordings found.[/yellow]")
            pause()
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

    finally:
        ssh.close()

    pause("Press Enter to return to the main menu...")


if __name__ == "__main__":
    main()
