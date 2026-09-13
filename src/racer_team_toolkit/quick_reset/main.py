"""Quick Reset menu entry point."""

from racer_team_toolkit.ui.functions import (
    pause,
    print_header,
    select_menu,
)

QUICK_RESET_HEADER = "Quick Reset"

QUICK_RESET_CHOICES = [
    "Quick Reset",
    "Custom Reset",
    "Return to Main Menu",
]


def main() -> None:
    """Display the Quick Reset menu."""

    print_header(QUICK_RESET_HEADER)

    user_choice = select_menu(
        "Select an option:",
        QUICK_RESET_CHOICES,
    )

    if user_choice == QUICK_RESET_CHOICES[0]:
        print_header("Quick Reset")
        print("Quick Reset - not implemented yet")

    elif user_choice == QUICK_RESET_CHOICES[1]:
        print_header("Custom Reset")
        print("Custom Reset - not implemented yet")

    elif user_choice == QUICK_RESET_CHOICES[2] or user_choice is None:
        return

    pause("Press Enter to return to the main menu...")
