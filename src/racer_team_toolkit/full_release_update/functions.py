"""Reusable operations for the full release update flow."""

from pathlib import Path

from racer_team_toolkit.apk_installer.functions import (
    InstallationResult,
    build_installation_plan,
    contains_apk_files,
    run_installation,
)
from racer_team_toolkit.config import AndroidDevice
from racer_team_toolkit.full_release_update.dataclasses import ReleaseUpdatePlan
from racer_team_toolkit.jar_management.config import JAR_FILENAME
from racer_team_toolkit.jar_management.functions import (
    folder_contains_groundlord_jar,
    upload_selected_jar,
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
        if contains_apk_files(downloads_path)
        or folder_contains_groundlord_jar(downloads_path)
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

    return [
        run_installation(item, console)
        for item in plan.apk_plan
    ]


def run_jar_update(plan: ReleaseUpdatePlan) -> bool | None:
    """Run the existing JAR upload flow for the preselected JAR."""

    if not plan.upload_jar:
        return None

    if plan.jar_file is None:
        return False

    return upload_selected_jar(plan.jar_file)
