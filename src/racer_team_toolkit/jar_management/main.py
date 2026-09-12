"""JAR Management menu entry point."""

from racer_team_toolkit.jar_management.functions import restart_jar, upload_jar
from racer_team_toolkit.ui.functions import (
    pause,
    print_header,
    select_menu,
)

JAR_MANAGEMENT_HEADER = "JAR Management"

JAR_MANAGEMENT_CHOICES = [
    "Restart JAR",
    "Upload JAR",
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
        if restart_jar():
            print("✓ Racer Groundlord restarted successfully.")
        else:
            print("[!] Failed to restart Racer Groundlord.")

    elif user_choice == JAR_MANAGEMENT_CHOICES[1]:
        print_header(JAR_MANAGEMENT_CHOICES[1])

        if upload_jar():
            print("✓ Racer Groundlord JAR uploaded and restarted successfully.")
        else:
            print("[!] Failed to upload Racer Groundlord JAR.")

    elif user_choice == JAR_MANAGEMENT_CHOICES[2]:
        return

    pause("Press Enter to return to the main menu...")
