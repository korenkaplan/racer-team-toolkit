"""Ronen Operations menu entry point."""

from racer_team_toolkit.imu_recordings.main import main as run_imu_recordings_main
from racer_team_toolkit.jar_management.config import (
    CAMERA_MODE_RTSP,
    CAMERA_MODE_SHARPEYE,
)
from racer_team_toolkit.jar_management.functions import (
    change_camera_mode,
    get_current_camera_mode,
    restart_jar,
    upload_jar,
)
from racer_team_toolkit.ui.functions import (
    console,
    pause,
    print_header,
    run_with_spinner,
    select_menu,
)

RONEN_OPERATIONS_HEADER = "Ronen Operations"

RONEN_OPERATIONS_CHOICES = [
    "Extract IMU Recordings",
    "Restart JAR",
    "Upload JAR",
    "Change Camera Source",
    "Return to Main Menu",
]


def show_camera_mode_indicator() -> None:
    """Display the currently configured camera source."""

    current_mode = run_with_spinner(
        "Checking current camera source...",
        get_current_camera_mode,
    )

    if current_mode is None:
        console.print("[yellow]Camera Source: Unknown / Unavailable[/yellow]")
        return

    console.print(f"[cyan]Camera Source:[/cyan] [bold]{current_mode}[/bold]")


def main() -> None:
    """Display the Ronen Operations menu and run the selected operation."""

    while True:
        print_header(RONEN_OPERATIONS_HEADER)
        show_camera_mode_indicator()
        console.print()

        user_choice = select_menu(
            "Select an option:",
            RONEN_OPERATIONS_CHOICES,
        )

        if user_choice == RONEN_OPERATIONS_CHOICES[0]:
            run_imu_recordings_main()

        elif user_choice == RONEN_OPERATIONS_CHOICES[1]:
            print_header(RONEN_OPERATIONS_CHOICES[1])

            if not restart_jar():
                print("[!] Failed to restart Racer Groundlord.")

            pause("Press Enter to return to Ronen Operations...")

        elif user_choice == RONEN_OPERATIONS_CHOICES[2]:
            print_header(RONEN_OPERATIONS_CHOICES[2])

            if upload_jar():
                print("✓ Racer Groundlord JAR uploaded and restarted successfully.")
            else:
                print("[!] Failed to upload Racer Groundlord JAR.")

            pause("Press Enter to return to Ronen Operations...")

        elif user_choice == RONEN_OPERATIONS_CHOICES[3]:
            print_header(RONEN_OPERATIONS_CHOICES[3])

            camera_choice = select_menu(
                "Select camera source:",
                [
                    CAMERA_MODE_SHARPEYE,
                    CAMERA_MODE_RTSP,
                    "Cancel",
                ],
            )

            if camera_choice in (CAMERA_MODE_SHARPEYE, CAMERA_MODE_RTSP):
                if change_camera_mode(camera_choice):
                    print(f"✓ Camera source changed to {camera_choice}.")
                else:
                    print(f"[!] Failed to change camera source to {camera_choice}.")

                pause("Press Enter to return to Ronen Operations...")

        elif user_choice == RONEN_OPERATIONS_CHOICES[4] or user_choice is None:
            return


if __name__ == "__main__":
    main()
