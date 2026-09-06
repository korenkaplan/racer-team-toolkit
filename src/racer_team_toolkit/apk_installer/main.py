"""Interactive APK installer flow."""

from pathlib import Path

from rich.table import Table
from rich.text import Text

from racer_team_toolkit.adb import get_connected_serials
from racer_team_toolkit.apk_installer.functions import (
    InstallationPlan,
    InstallationResult,
    build_installation_plan,
    get_folders_in_downloads,
    run_installation,
)
from racer_team_toolkit.config import (
    APK_INSTALLER_APPROVAL_CHOICES,
    APK_INSTALLER_HEADER,
    DEVICES_REGISTRY,
)
from racer_team_toolkit.ui.functions import (
    console,
    pause,
    print_error,
    print_header,
    select_menu,
    select_menu_tuple,
)


def main() -> None:
    """Run folder selection, approval, installation, and result reporting."""

    print_header("APK Installer!")
    connected_devices = [
        device for device in DEVICES_REGISTRY if device.serial in get_connected_serials()
    ]

    if not connected_devices:
        print_error("No Devices Are Connected. Please connect a device and try again.")
        pause("Press Enter to return to the main menu...")
        return

    folders = get_folders_in_downloads()
    while True:
        folder = choose_folder(folders)
        plan = build_installation_plan(folder, connected_devices)
        print_installation_plan(plan)
        approval = select_menu("Install the APKs shown above?", APK_INSTALLER_APPROVAL_CHOICES)

        if approval == "Choose another folder":
            continue
        if approval != "Yes":
            return

        results = [run_installation(item, console) for item in plan]
        print_installation_results(results)
        return


def choose_folder(folders: list[Path]) -> Path:
    """Prompt the user to choose Downloads or one of its direct child folders."""

    choices = [path.name for path in folders]
    folder_index, _ = select_menu_tuple(APK_INSTALLER_HEADER, choices)
    return folders[folder_index]


def print_installation_plan(plan: list[InstallationPlan]) -> None:
    """Render the proposed APK for each connected device."""

    table = Table(title="Installation Plan", show_lines=True)
    table.add_column("Device")
    table.add_column("Installation File")

    for item in plan:
        if item.apk_path is None:
            table.add_row(
                Text(item.device.name, style="red"),
                Text("NO MATCHING APK FOUND", style="red"),
            )
        else:
            table.add_row(item.device.name, item.apk_path.name)

    console.print(table)


def print_installation_results(results: list[InstallationResult]) -> None:
    """Render per-device installation results and totals."""

    table = Table(title="Installation Results", show_lines=True)
    table.add_column("Device")
    table.add_column("Result")

    status_text = {
        "success": ("✓ Success", "green"),
        "failed": ("✗ Failed", "red"),
        "skipped": ("⚠ Skipped", "yellow"),
    }

    for result in results:
        label, color = status_text[result.status]
        result_text = label
        if result.status == "failed" and result.message:
            result_text = f"{label}\n{result.message}"
        table.add_row(result.device.name, Text(result_text, style=color))

    console.print(table)
    console.print("APK installation completed.")
    console.print(f"Successful: {sum(result.status == 'success' for result in results)}")
    console.print(f"Failed:     {sum(result.status == 'failed' for result in results)}")
    console.print(f"Skipped:    {sum(result.status == 'skipped' for result in results)}")


if __name__ == "__main__":
    main()
