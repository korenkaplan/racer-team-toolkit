"""Reusable operations for the full release update flow."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.table import Table
from rich.text import Text

from racer_team_toolkit.apk_installer.functions import (
    InstallationResult,
    build_installation_plan,
    contains_apk_files,
    get_folders_in_downloads,
)
from racer_team_toolkit.apk_installer.main import install_with_progress
from racer_team_toolkit.config import AndroidDevice
from racer_team_toolkit.full_release_update.dataclasses import ReleaseUpdatePlan
from racer_team_toolkit.jar_management.config import JAR_FILENAME
from racer_team_toolkit.jar_management.functions import (
    select_jar_file,
    upload_selected_jar,
)
from racer_team_toolkit.ssh.functions import is_ssh_server_reachable
from racer_team_toolkit.ui.functions import (
    console,
    print_error,
    select_menu,
    select_menu_tuple,
)


def get_release_folders() -> list[Path]:
    """Return Downloads locations containing direct APK or JAR files."""

    downloads_path = Path.home() / "Downloads"
    excluded_suffixes = {
        ".app",
        ".download",
        ".bundle",
        ".framework",
    }

    def contains_release_files(
        folder: Path,
    ) -> bool:
        has_apk = contains_apk_files(
            folder,
        )

        has_jar = (folder / JAR_FILENAME).is_file()

        return has_apk or has_jar

    folders = [
        path
        for path in downloads_path.iterdir()
        if path.is_dir()
        and path.suffix.lower() not in excluded_suffixes
        and contains_release_files(path)
    ]

    matching_locations = [downloads_path] if contains_release_files(downloads_path) else []

    return [
        *matching_locations,
        *sorted(folders),
    ]


def find_groundlord_jar(
    folder: Path,
) -> Path | None:
    """Return the Groundlord JAR directly from the selected folder."""

    jar_path = folder / JAR_FILENAME

    if jar_path.is_file():
        return jar_path

    return None


def build_release_update_plan(
    release_folder: Path,
    connected_devices: list[AndroidDevice],
) -> ReleaseUpdatePlan:
    """Build the initial update plan from the selected release folder."""

    ronen_connected = is_ssh_server_reachable(timeout=2.0)
    jar_file = find_groundlord_jar(release_folder) if ronen_connected else None

    return ReleaseUpdatePlan(
        connected_devices=connected_devices,
        apk_plan=build_installation_plan(
            release_folder,
            connected_devices,
        ),
        apk_source_folder=release_folder,
        jar_file=jar_file,
        jar_source_folder=release_folder if jar_file is not None else None,
        install_apk=bool(connected_devices),
        ronen_connected=ronen_connected,
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
    plan.upload_jar = plan.ronen_connected


def skip_jar_upload(plan: ReleaseUpdatePlan) -> None:
    """Disable JAR upload for this release update."""

    plan.upload_jar = False


def run_apk_updates(
    plan: ReleaseUpdatePlan,
    console,
) -> list[InstallationResult]:
    """Install APKs concurrently with per-device Rich progress."""

    if not plan.install_apk:
        return []

    return install_with_progress(plan.apk_plan)


def run_jar_update(plan: ReleaseUpdatePlan) -> bool | None:
    """Run the existing JAR upload flow for the preselected JAR."""

    if not plan.ronen_connected or not plan.upload_jar:
        return None

    if plan.jar_file is None:
        return False

    try:
        return upload_selected_jar(plan.jar_file, show_progress=False)
    except Exception as error:
        print_error(f"JAR update failed: {error}")
        return False


def print_release_update_results(
    plan: ReleaseUpdatePlan,
    apk_results: list[InstallationResult],
    jar_result: bool | None,
) -> None:
    """Display the final results of the full release update."""

    table = Table(
        title="Full Release Update Results",
        show_lines=True,
    )

    table.add_column("Component")
    table.add_column("Target")
    table.add_column("Result")

    apk_results_by_serial = {result.device.serial: result for result in apk_results}

    for item in plan.apk_plan:
        if not plan.install_apk:
            result_text = Text(
                "SKIPPED",
                style="yellow",
            )

        elif item.apk_path is None:
            result_text = Text(
                "SKIPPED - No matching APK",
                style="yellow",
            )

        else:
            result = apk_results_by_serial.get(
                item.device.serial,
            )

            if result is None:
                result_text = Text(
                    "NOT RUN",
                    style="yellow",
                )

            elif result.status == "success":
                result_text = Text(
                    f"SUCCESS WITH WARNINGS\n{result.message}" if result.message else "SUCCESS",
                    style="yellow" if result.message else "green",
                )

            elif result.status == "skipped":
                result_text = Text(
                    "SKIPPED",
                    style="yellow",
                )

            else:
                message = f"FAILED\n{result.message}" if result.message else "FAILED"

                result_text = Text(
                    message,
                    style="red",
                )

        table.add_row(
            "APK",
            item.device.name,
            result_text,
        )

    if plan.ronen_connected:
        if not plan.upload_jar:
            jar_result_text = Text(
                "SKIPPED",
                style="yellow",
            )

        elif jar_result is True:
            jar_result_text = Text(
                "SUCCESS",
                style="green",
            )

        elif jar_result is False:
            jar_result_text = Text(
                "FAILED",
                style="red",
            )

        else:
            jar_result_text = Text(
                "NOT RUN",
                style="yellow",
            )

        table.add_row(
            "JAR",
            "Racer Groundlord",
            jar_result_text,
        )

    console.print()
    console.print(table)


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

    if not plan.ronen_connected or plan.jar_file is not None:
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

    if plan.ronen_connected:
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


def execute_release_update(
    plan: ReleaseUpdatePlan,
) -> None:
    """Run independent JAR and APK updates concurrently, then report both."""

    console.print()
    console.rule("[bold]APK and JAR Updates[/bold]")
    with ThreadPoolExecutor(max_workers=1) as executor:
        jar_future = executor.submit(run_jar_update, plan)
        try:
            apk_results = run_apk_updates(plan, console)
        except Exception as error:
            apk_results = [
                InstallationResult(item.device, "failed", str(error))
                for item in plan.apk_plan
                if item.apk_path is not None
            ]
        jar_result = jar_future.result()

    print_release_update_results(plan, apk_results, jar_result)


def prepare_release_update(
    connected_devices: list[AndroidDevice],
) -> ReleaseUpdatePlan | None:
    """Select a release folder and display the final release update plan once."""

    release_folders = get_release_folders()

    if not release_folders:
        print_error("No release folders containing APK or JAR files were found in Downloads.")
        return None

    release_folder = choose_release_folder(
        release_folders,
    )

    plan = build_release_update_plan(
        release_folder,
        connected_devices,
    )

    console.print()
    console.print(f"Selected release folder: [bold]{release_folder}[/bold]")

    if not resolve_missing_apks(plan):
        return None

    if not resolve_missing_jar(plan):
        return None

    console.print()

    print_release_update_plan(
        plan,
    )

    return plan
