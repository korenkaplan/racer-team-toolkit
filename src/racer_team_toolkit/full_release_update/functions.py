"""Reusable operations for the full release update flow."""

from pathlib import Path

from rich.table import Table
from rich.text import Text

from racer_team_toolkit.apk_installer.functions import (
    InstallationResult,
    build_installation_plan,
    contains_apk_files,
    get_folders_in_downloads,
    run_installation,
)
from racer_team_toolkit.config import AndroidDevice
from racer_team_toolkit.full_release_update.dataclasses import ReleaseUpdatePlan
from racer_team_toolkit.jar_management.config import JAR_FILENAME
from racer_team_toolkit.jar_management.functions import (
    folder_contains_groundlord_jar,
    select_jar_file,
    upload_selected_jar,
)
from racer_team_toolkit.ui.functions import (
    console,
    print_error,
    select_menu,
    select_menu_tuple,
)


def get_release_folders() -> list[Path]:
    """Return Downloads locations that contain APK files or the Groundlord JAR."""

    downloads_path = Path.home() / "Downloads"
    excluded_suffixes = {".app", ".download", ".bundle", ".framework"}

    folders = [
        path
        for path in downloads_path.iterdir()
        if path.is_dir()
        and path.suffix.lower() not in excluded_suffixes
        and (contains_apk_files(path) or folder_contains_groundlord_jar(path))
    ]

    matching_locations = (
        [downloads_path]
        if contains_apk_files(downloads_path) or folder_contains_groundlord_jar(downloads_path)
        else []
    )

    return [*matching_locations, *sorted(folders)]


def find_groundlord_jar(folder: Path) -> Path | None:
    """Return the Groundlord JAR from a release folder, if present."""

    return next(
        (
            path
            for path in folder.rglob(JAR_FILENAME)
            if path.is_file() and path.name == JAR_FILENAME
        ),
        None,
    )


def build_release_update_plan(
    release_folder: Path,
    connected_devices: list[AndroidDevice],
) -> ReleaseUpdatePlan:
    """Build the initial update plan from the selected release folder."""

    jar_file = find_groundlord_jar(release_folder)

    return ReleaseUpdatePlan(
        connected_devices=connected_devices,
        apk_plan=build_installation_plan(
            release_folder,
            connected_devices,
        ),
        apk_source_folder=release_folder,
        jar_file=jar_file,
        jar_source_folder=release_folder if jar_file is not None else None,
        install_apk=True,
        upload_jar=jar_file is not None,
    )


def has_matching_apk_files(plan: ReleaseUpdatePlan) -> bool:
    """Return whether at least one connected device has a matching APK."""

    return any(item.apk_path is not None for item in plan.apk_plan)


def has_missing_apk_files(plan: ReleaseUpdatePlan) -> bool:
    """Return whether at least one connected device has no matching APK."""

    return any(item.apk_path is None for item in plan.apk_plan)


def change_apk_folder(
    plan: ReleaseUpdatePlan,
    folder: Path,
) -> None:
    """Replace the APK source folder and rebuild the per-device APK plan."""

    plan.apk_source_folder = folder
    plan.apk_plan = build_installation_plan(
        folder,
        plan.connected_devices,
    )
    plan.install_apk = True


def skip_apk_install(plan: ReleaseUpdatePlan) -> None:
    """Disable APK installation for this release update."""

    plan.install_apk = False


def change_jar_file(
    plan: ReleaseUpdatePlan,
    jar_file: Path,
) -> None:
    """Replace the selected JAR and remember its containing folder."""

    plan.jar_file = jar_file
    plan.jar_source_folder = jar_file.parent
    plan.upload_jar = True


def skip_jar_upload(plan: ReleaseUpdatePlan) -> None:
    """Disable JAR upload for this release update."""

    plan.upload_jar = False


def run_apk_updates(
    plan: ReleaseUpdatePlan,
    console,
) -> list[InstallationResult]:
    """Run the existing APK installation flow for the selected APK plan."""

    if not plan.install_apk:
        return []

    return [run_installation(item, console) for item in plan.apk_plan]


def run_jar_update(plan: ReleaseUpdatePlan) -> bool | None:
    """Run the existing JAR upload flow for the preselected JAR."""

    if not plan.upload_jar:
        return None

    if plan.jar_file is None:
        return False

    return upload_selected_jar(plan.jar_file)


def choose_apk_folder(
    folders: list[Path],
) -> Path:
    """Let the user choose a folder containing APK files."""

    choices = [folder.name for folder in folders]

    folder_index, _ = select_menu_tuple(
        "Select APK folder:",
        choices,
    )

    return folders[folder_index]


def resolve_missing_apks(
    plan: ReleaseUpdatePlan,
) -> bool:
    """Resolve missing APKs before running the update."""

    while plan.install_apk and has_missing_apk_files(plan):
        choices = [
            "Choose another APK folder",
        ]

        if has_matching_apk_files(plan):
            choices.append("Continue with available APKs")

        choices.extend(
            [
                "Skip all APK updates",
                "Cancel",
            ]
        )

        choice = select_menu(
            "One or more matching APKs are missing:",
            choices,
        )

        if choice == "Choose another APK folder":
            apk_folders = get_folders_in_downloads()

            if not apk_folders:
                print_error("No folders containing APK files were found.")
                continue

            apk_folder = choose_apk_folder(
                apk_folders,
            )

            change_apk_folder(
                plan,
                apk_folder,
            )

            print_release_update_plan(
                plan,
            )

        elif choice == "Continue with available APKs":
            return True

        elif choice == "Skip all APK updates":
            skip_apk_install(
                plan,
            )
            return True

        else:
            return False

    return True


def resolve_missing_jar(
    plan: ReleaseUpdatePlan,
) -> bool:
    """Resolve a missing JAR before running the update."""

    if plan.jar_file is not None:
        return True

    while True:
        choice = select_menu(
            "Racer Groundlord JAR was not found:",
            [
                "Choose another JAR",
                "Skip JAR upload",
                "Cancel",
            ],
        )

        if choice == "Choose another JAR":
            jar_file = select_jar_file()

            if jar_file is None:
                continue

            change_jar_file(
                plan,
                jar_file,
            )

            print_release_update_plan(
                plan,
            )

            return True

        if choice == "Skip JAR upload":
            skip_jar_upload(
                plan,
            )
            return True

        return False


def print_release_update_plan(
    plan: ReleaseUpdatePlan,
) -> None:
    """Display the APK and JAR files selected for the release update."""

    table = Table(
        title="Full Release Update Plan",
        show_lines=True,
    )

    table.add_column("Component")
    table.add_column("Target")
    table.add_column("File")
    table.add_column("Action")

    for item in plan.apk_plan:
        if item.apk_path is None:
            file_text = Text(
                "NO MATCHING APK FOUND",
                style="red",
            )
            action_text = Text(
                "SKIP",
                style="yellow",
            )

        elif not plan.install_apk:
            file_text = item.apk_path.name
            action_text = Text(
                "SKIP",
                style="yellow",
            )

        else:
            file_text = item.apk_path.name
            action_text = Text(
                "INSTALL",
                style="green",
            )

        table.add_row(
            "APK",
            item.device.name,
            file_text,
            action_text,
        )

    if plan.jar_file is None:
        jar_file_text = Text(
            "JAR NOT FOUND",
            style="red",
        )
        jar_action_text = Text(
            "SKIP",
            style="yellow",
        )

    elif not plan.upload_jar:
        jar_file_text = plan.jar_file.name
        jar_action_text = Text(
            "SKIP",
            style="yellow",
        )

    else:
        jar_file_text = plan.jar_file.name
        jar_action_text = Text(
            "UPLOAD",
            style="green",
        )

    table.add_row(
        "JAR",
        "Racer Groundlord",
        jar_file_text,
        jar_action_text,
    )

    console.print()
    console.print(table)


def choose_release_folder(
    folders: list[Path],
) -> Path:
    """Let the user choose a release folder."""

    choices = [folder.name for folder in folders]

    folder_index, _ = select_menu_tuple(
        "Select release folder:",
        choices,
    )

    return folders[folder_index]
