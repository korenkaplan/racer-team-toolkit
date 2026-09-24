"""JAR Management menu entry point."""

from racer_team_toolkit.jar_management.config import (
    CAMERA_MODE_RTSP,
    CAMERA_MODE_SHARPEYE,
)
from racer_team_toolkit.jar_management.functions import (
    change_camera_mode,
    restart_jar,
    upload_jar,
)
from racer_team_toolkit.ui.functions import (
    pause,
    print_header,
    select_menu,
)

JAR_MANAGEMENT_HEADER = "JAR Management"

JAR_MANAGEMENT_CHOICES = [
    "Restart JAR",
    "Upload JAR",
    "Change Camera Source",
    "Return to Main Menu",
]


def main() -> None:
    """Display the JAR Management menu and run the selected operation."""

    print_header(JAR_MANAGEMENT_HEADER)

    user_choice = select_menu(
        "Select an option:",
        JAR_MANAGEMENT_CHOICES,
    )

    if user_choice == JAR_MANAGEMENT_CHOICES[0]:
        print_header(JAR_MANAGEMENT_CHOICES[0])

        if not restart_jar():
            print("[!] Failed to restart Racer Groundlord.")

    elif user_choice == JAR_MANAGEMENT_CHOICES[1]:
        print_header(JAR_MANAGEMENT_CHOICES[1])

        if upload_jar():
            print("✓ Racer Groundlord JAR uploaded and restarted successfully.")
        else:
            print("[!] Failed to upload Racer Groundlord JAR.")

    elif user_choice == JAR_MANAGEMENT_CHOICES[2]:
        print_header(JAR_MANAGEMENT_CHOICES[2])

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

    elif user_choice == JAR_MANAGEMENT_CHOICES[3] or user_choice is None:
        return

    pause("Press Enter to return to the main menu...")


if __name__ == "__main__":
    main()
