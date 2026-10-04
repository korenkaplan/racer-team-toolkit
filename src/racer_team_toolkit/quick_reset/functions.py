"""Quick Reset functions."""

from collections.abc import Callable
from dataclasses import dataclass
from shlex import quote

import questionary
from rich.console import Console
from rich.live import Live
from rich.table import Table

from racer_team_toolkit.adb import (
    get_connected_android_devices,
    run_adb_command,
)
from racer_team_toolkit.config import (
    REFF_REMOTE_PATHS,
    VIDEO_REMOTE_PATHS,
    AndroidDevice,
)
from racer_team_toolkit.multithreading.functions import run_tasks
from racer_team_toolkit.multithreading.updates import run_with_updates
from racer_team_toolkit.ui.functions import run_with_spinner
from racer_team_toolkit.ui.status_table import DeviceStatusTable

console = Console()


def select_devices(
    devices: list[AndroidDevice],
) -> list[AndroidDevice]:
    """Let the user select connected devices or choose all devices."""

    if not devices:
        return []

    all_value = "__all__"

    selected_values = questionary.checkbox(
        "Select devices (Space to select, Enter to continue):",
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


def build_reset_plan_counts(
    devices: list[AndroidDevice],
    reset_plan: dict[str, set[str]],
) -> dict[str, dict[str, int]]:
    """Count files for each selected folder in the reset plan."""

    counts: dict[str, dict[str, int]] = {}

    for device in devices:
        selected_folders = reset_plan.get(
            device.serial,
            set(),
        )

        device_counts = {
            "reff": 0,
            "videos": 0,
        }

        if "reff" in selected_folders:
            device_counts["reff"] = sum(
                count_remote_files(
                    device,
                    remote_path,
                )
                for remote_path in REFF_REMOTE_PATHS
            )

        if "videos" in selected_folders:
            device_counts["videos"] = sum(
                count_remote_files(
                    device,
                    remote_path,
                )
                for remote_path in VIDEO_REMOTE_PATHS
            )

        counts[device.serial] = device_counts

    return counts


def print_reset_plan(
    devices: list[AndroidDevice],
    reset_plan: dict[str, set[str]],
    counts: dict[str, dict[str, int]],
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

        device_counts = counts.get(
            device.serial,
            {
                "reff": 0,
                "videos": 0,
            },
        )

        reff_display = "-"
        videos_display = "-"

        if "reff" in selected_folders:
            reff_count = device_counts["reff"]
            total_files += reff_count
            reff_display = f"✓ {reff_count} files"

        if "videos" in selected_folders:
            video_count = device_counts["videos"]
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


def reset_remote_folder(
    device: AndroidDevice,
    remote_path: str,
) -> bool:
    """Delete all contents of a remote Android folder.

    Missing source folders are treated as already empty because different
    Android versions may create different recording paths.
    """

    path = quote(remote_path)
    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            f"if [ -d {path} ]; then find {path} -mindepth 1 -delete; else exit 0; fi",
        ]
    )
    return result.returncode == 0


@dataclass(frozen=True)
class ResetUpdate:
    serial: str
    folder: str
    message: str
    completed: int
    total: int
    status: str


@dataclass(frozen=True)
class ResetResult:
    device: AndroidDevice
    errors: tuple[str, ...]

    @property
    def succeeded(self) -> bool:
        return not self.errors


def reset_steps(folders: set[str]) -> list[tuple[str, str]]:
    """Use one stable folder order in CLI and GUI."""
    return [
        (label, path)
        for key, label, paths in (
            ("reff", "REFF", REFF_REMOTE_PATHS),
            ("videos", "Screen Videos", VIDEO_REMOTE_PATHS),
        )
        if key in folders
        for path in dict.fromkeys(paths)
    ]


def reset_devices(
    devices: list[AndroidDevice],
    reset_plan: dict[str, set[str]],
    *,
    status_callback: Callable[[ResetUpdate], None] | None = None,
) -> list[ResetResult]:
    """One worker per selected device; wait for every worker before returning.

    Paths within a device stay sequential. Workers only emit events, never UI.
    A failed path does not prevent the remaining paths or devices from running.
    """
    selected = [d for d in devices if reset_steps(reset_plan.get(d.serial, set()))]
    if not selected:
        return []

    def worker(device: AndroidDevice) -> ResetResult:
        steps = reset_steps(reset_plan[device.serial])
        errors: list[str] = []
        failed_folders: set[str] = set()

        def report(folder: str, message: str, completed: int, status: str) -> None:
            if status_callback is not None:
                status_callback(
                    ResetUpdate(device.serial, folder, message, completed, len(steps), status)
                )

        for index, (label, path) in enumerate(steps):
            report(label, f"Resetting {path}", index, "Running")
            try:
                success = reset_remote_folder(device, path)
                detail = "Reset command failed"
            except Exception as error:
                success = False
                detail = f"{type(error).__name__}: {error}"
            if not success:
                errors.append(f"{path}: {detail}")
                failed_folders.add(label)
            last_in_folder = index + 1 == len(steps) or steps[index + 1][0] != label
            message = (
                ("Failed" if label in failed_folders else "Done") if last_in_folder else "Running"
            )
            status = ("Failed" if errors else "Done") if index + 1 == len(steps) else "Running"
            report(label, message, index + 1, status)
        return ResetResult(device, tuple(errors))

    results = run_tasks(selected, worker, max_workers=len(selected))
    return [
        result.value
        if result.succeeded and result.value is not None
        else ResetResult(result.item, (str(result.error or "Worker returned no result"),))
        for result in results
    ]


def apply_reset_plan(
    devices: list[AndroidDevice],
    reset_plan: dict[str, set[str]],
) -> bool:
    """Render live statuses on the calling thread until every device finishes."""
    selected = [d for d in devices if reset_steps(reset_plan.get(d.serial, set()))]
    table = DeviceStatusTable(
        "Folder Reset Status",
        {d.serial: d.name for d in selected},
        ["REFF", "Screen Videos", "Progress", "Status"],
    )
    for device in selected:
        cells = {label: "Waiting" for label, _ in reset_steps(reset_plan[device.serial])}
        table.update(
            device.serial,
            **cells,
            Progress="0/" + str(len(reset_steps(reset_plan[device.serial]))),
            Status="Waiting",
        )
    with Live(table.render(), console=console, auto_refresh=False) as live:

        def update(event: ResetUpdate) -> None:
            table.update(
                event.serial,
                **{event.folder: event.message},
                Progress=f"{event.completed}/{event.total}",
                Status=event.status,
            )

        results = run_with_updates(
            lambda report: reset_devices(selected, reset_plan, status_callback=report),
            update,
            lambda: live.update(table.render(), refresh=True),
        )
        for result in results:
            table.update(result.device.serial, Status="Done" if result.succeeded else "Failed")
        live.update(table.render(), refresh=True)
    for result in results:
        for error in result.errors:
            console.print(f"{result.device.name}: {error}", style="red", markup=False)
    return all(result.succeeded for result in results)


def confirm_reset() -> bool:
    """Ask the user to confirm the reset operation."""

    return (
        questionary.confirm(
            "Continue with reset?",
            default=False,
        ).ask()
        is True
    )


def custom_reset() -> None:
    """Run the Custom Reset flow."""

    devices = run_with_spinner(
        "Checking connected devices...",
        get_connected_android_devices,
    )

    if not devices:
        console.print("[yellow]No supported Android devices are connected.[/yellow]")
        return

    selected_devices = select_devices(devices)

    if not selected_devices:
        console.print("[yellow]No devices selected.[/yellow]")
        return

    reset_plan = build_custom_reset_plan(selected_devices)

    if not reset_plan:
        console.print("[yellow]No folders selected.[/yellow]")
        return

    counts = run_with_spinner(
        "Checking selected folders...",
        build_reset_plan_counts,
        selected_devices,
        reset_plan,
    )

    total_files = print_reset_plan(
        selected_devices,
        reset_plan,
        counts,
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


def quick_reset() -> None:
    """Reset REFF and Screen Videos for all connected devices."""

    devices = run_with_spinner(
        "Checking connected devices...",
        get_connected_android_devices,
    )

    if not devices:
        console.print("[yellow]No supported Android devices are connected.[/yellow]")
        return

    reset_plan = {device.serial: {"reff", "videos"} for device in devices}

    counts = run_with_spinner(
        "Checking folders...",
        build_reset_plan_counts,
        devices,
        reset_plan,
    )

    total_files = print_reset_plan(
        devices,
        reset_plan,
        counts,
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
