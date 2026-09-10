"""Menu entry point for REFF extraction options."""

from racer_team_toolkit.config import (
    REFF_EXTRACTOR_CHOICES,
    REFF_EXTRACTOR_HEADER,
)
from racer_team_toolkit.reff_extractor.functions import (
    extract_reff,
    extract_reff_and_videos,
)
from racer_team_toolkit.ui.functions import (
    pause,
    print_header,
    select_menu,
)

def main() -> None:
    print_header(REFF_EXTRACTOR_HEADER)

    user_choice = select_menu(
        "Select an option:",
        REFF_EXTRACTOR_CHOICES,
    )

    if user_choice == REFF_EXTRACTOR_CHOICES[0]:
        print_header(REFF_EXTRACTOR_CHOICES[0])
        extract_reff()

    elif user_choice == REFF_EXTRACTOR_CHOICES[1]:
        print_header(REFF_EXTRACTOR_CHOICES[1])
        extract_reff_and_videos()

    elif user_choice == REFF_EXTRACTOR_CHOICES[2]:
        return

    pause("Press Enter to return to the main menu...")
    print_header(REFF_EXTRACTOR_HEADER)

    user_choice = select_menu(
        "Select an option:",
        REFF_EXTRACTOR_CHOICES,
    )

    if user_choice == REFF_EXTRACTOR_CHOICES[0]:
        print_header(REFF_EXTRACTOR_CHOICES[0])
        extract_reff()

    elif user_choice == REFF_EXTRACTOR_CHOICES[1]:
        print_header(REFF_EXTRACTOR_CHOICES[1])
        extract_reff_and_videos()

    pause("Press Enter to return to the main menu...")