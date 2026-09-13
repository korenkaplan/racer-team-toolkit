"""Quick Reset functions."""

import questionary
from rich.console import Console
from rich.table import Table

from racer_team_toolkit.adb import get_connected_android_devices, run_adb_command
from racer_team_toolkit.config import VIDEO_REMOTE_PATH, AndroidDevice

console = Console()


def select_devices(
    devices: list[AndroidDevice],
) -> list[AndroidDevice]:
    """Let the user select connected devices or choose all devices."""

    if not devices:
        return []

    all_value = "__all__"

    selected_values = questionary.checkbox(
        "Select devices:",
        choices=[
            questionary.Choice(
                title="All Connected Devices",
                value=all_value,
            ),
            *[
                questionary.Choice(
                    title=device.name,
                    value=device.serial,
                )
                for device in devices
            ],
        ],
    ).ask()

    if not selected_values:
        return []

    if all_value in selected_values:
        return devices

    return [device for device in devices if device.serial in selected_values]


def custom_reset() -> None:
    """Run the Custom Reset flow."""

    devices = get_connected_android_devices()

    if not devices:
        print("[!] No supported Android devices are connected.")
        return

    selected_devices = select_devices(devices)

    if not selected_devices:
        print("[!] No devices selected.")
        return

    reset_plan = build_custom_reset_plan(selected_devices)

    if not reset_plan:
        print("[!] No folders selected.")
        return

    print("\nReset plan:")

    total_files = print_reset_plan(
        selected_devices,
        reset_plan,
    )

    if total_files == 0:
        console.print("\n[yellow]Selected folders are already empty.[/yellow]")
        return

    if not confirm_reset():
        console.print("\n[yellow]Reset cancelled.[/yellow]")
        return

    success = apply_reset_plan(
        selected_devices,
        reset_plan,
    )

    console.print()

    if success:
        console.print("[bold green]✓ Custom Reset completed successfully.[/bold green]")
    else:
        console.print("[bold red]✗ Custom Reset completed with errors.[/bold red]")


def select_folders_for_device(
    device: AndroidDevice,
) -> set[str]:
    """Let the user choose which folders to reset for one device."""

    selected_folders = questionary.checkbox(
        f"{device.name} - Select folders (Space to select, Enter to continue):",
        choices=[
            questionary.Choice(
                title="REFF",
                value="reff",
            ),
            questionary.Choice(
                title="Screen Videos",
                value="videos",
            ),
        ],
    ).ask()

    if not selected_folders:
        return set()

    return set(selected_folders)


def build_custom_reset_plan(
    devices: list[AndroidDevice],
) -> dict[str, set[str]]:
    """Build the per-device folder reset plan."""

    reset_plan: dict[str, set[str]] = {}

    for device in devices:
        selected_folders = select_folders_for_device(device)

        if selected_folders:
            reset_plan[device.serial] = selected_folders

    return reset_plan


def count_remote_files(
    device: AndroidDevice,
    remote_path: str,
) -> int:
    """Return the number of files under a remote Android directory."""

    result = run_adb_command(
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "find",
            remote_path,
            "-type",
            "f",
        ]
    )

    if result.returncode != 0:
        return 0

    return len([line for line in result.stdout.splitlines() if line.strip()])


def print_reset_plan(
    devices: list[AndroidDevice],
    reset_plan: dict[str, set[str]],
) -> int:
    """Display the reset plan and return the total number of files."""

    table = Table(
        title="Reset Plan",
        show_lines=True,
    )

    table.add_column("Device")
    table.add_column("REFF")
    table.add_column("Screen Videos")

    total_files = 0

    for device in devices:
        selected_folders = reset_plan.get(
            device.serial,
            set(),
        )

        reff_display = "-"
        videos_display = "-"

        if "reff" in selected_folders:
            reff_count = count_remote_files(
                device,
                device.remote_log_path,
            )
            total_files += reff_count
            reff_display = f"✓ {reff_count} files"

        if "videos" in selected_folders:
            video_count = count_remote_files(
                device,
                VIDEO_REMOTE_PATH,
            )
            total_files += video_count
            videos_display = f"✓ {video_count} files"

        table.add_row(
            device.name,
            reff_display,
            videos_display,
        )

    console.print()
    console.print(table)
    console.print(f"\n[bold]Total files to delete: {total_files}[/bold]")

    return total_files


def apply_reset_plan(
    devices: list[AndroidDevice],
    reset_plan: dict[str, set[str]],
) -> bool:
    """Apply the selected folder reset plan."""

    all_successful = True

    for device in devices:
        selected_folders = reset_plan.get(
            device.serial,
            set(),
        )

        if not selected_folders:
            continue

        console.rule(f"[bold]{device.name}[/bold]")

        if "reff" in selected_folders:
            success = reset_remote_folder(
                device,
                device.remote_log_path,
            )

            if success:
                console.print("[green]✓[/green] REFF folder reset")
            else:
                console.print("[red]✗[/red] Failed to reset REFF folder")
                all_successful = False

        if "videos" in selected_folders:
            success = reset_remote_folder(
                device,
                VIDEO_REMOTE_PATH,
            )

            if success:
                console.print("[green]✓[/green] Screen Videos folder reset")
            else:
                console.print("[red]✗[/red] Failed to reset Screen Videos folder")
                all_successful = False

    return all_successful


def reset_remote_folder(
    device: AndroidDevice,
    remote_path: str,
) -> bool:
    """Delete all contents of a remote Android folder."""

    result = run_adb_command(
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "find",
            remote_path,
            "-mindepth",
            "1",
            "-delete",
        ]
    )

    return result.returncode == 0


def confirm_reset() -> bool:
    """Ask the user to confirm the reset operation."""

    return questionary.confirm(
        "Continue with reset?",
        default=False,
    ).ask()


def quick_reset() -> None:
    """Reset REFF and Screen Videos for all connected devices."""

    devices = get_connected_android_devices()

    if not devices:
        console.print("[yellow]No supported Android devices are connected.[/yellow]")
        return

    reset_plan = {device.serial: {"reff", "videos"} for device in devices}

    total_files = print_reset_plan(
        devices,
        reset_plan,
    )

    if total_files == 0:
        console.print("\n[yellow]All folders are already empty.[/yellow]")
        return

    if not confirm_reset():
        console.print("\n[yellow]Reset cancelled.[/yellow]")
        return

    success = apply_reset_plan(
        devices,
        reset_plan,
    )

    console.print()

    if success:
        console.print("[bold green]✓ Quick Reset completed successfully.[/bold green]")
    else:
        console.print("[bold red]✗ Quick Reset completed with errors.[/bold red]")
