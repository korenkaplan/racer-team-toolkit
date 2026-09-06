from racer_team_toolkit.apk_installer.functions import get_folders_in_downloads
from racer_team_toolkit.config import JAR_MANAGEMENT_CHOICES, JAR_MANAGEMENT_HEADER
from racer_team_toolkit.jar_management.functions import (
    check_if_jar_exists_in_folder,
    check_server_status,
)
from racer_team_toolkit.ui.functions import print_header, select_menu, select_menu_tuple

FOLDER_IN_DOWNLOADS_WITH_FULL_PATH = get_folders_in_downloads()
FOLDERS_IN_DOWNLOADS = [path.name for path in FOLDER_IN_DOWNLOADS_WITH_FULL_PATH]


def main() -> None:
    print_header("JAR Management!")
    user_choice = select_menu(JAR_MANAGEMENT_HEADER, JAR_MANAGEMENT_CHOICES)

    if not check_server_status():
        print("[-] No connected server found. Please ensure the server is running and connected.")
        # wait for user input before returning to main menu

    if user_choice == JAR_MANAGEMENT_CHOICES[0]:  # Upload JAR
        # prompt user to select a folder from downloads
        folder_index, folder_name = select_menu_tuple(
            "Select a folder to upload JAR from:", FOLDERS_IN_DOWNLOADS
        )

        # check if the folder contains a JAR file
        check_if_jar_exists_in_folder(FOLDER_IN_DOWNLOADS_WITH_FULL_PATH[folder_index])

        # if a JAR file exists, upload it to the server

        # else print a message that no JAR file was found in the selected folder

        # wait for user input before returning to main menu
        pass

    elif user_choice == JAR_MANAGEMENT_CHOICES[1]:  # Restart JAR
        # restart the JAR file on the server

        # if the restart is successful, print a success message

        # else print a message that the restart failed

        # wait for user input before returning to main menu
        pass
    elif user_choice == JAR_MANAGEMENT_CHOICES[2]:  # Return to Main Menu
        pass
