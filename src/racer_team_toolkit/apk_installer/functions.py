"""Reusable APK installer operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

from racer_team_toolkit.adb.functions import run_adb_command
from racer_team_toolkit.config import AndroidDevice


@dataclass
class InstallationPlan:
    """APK selected for one connected device, if a match exists."""

    device: AndroidDevice
    apk_path: Optional[Path]


@dataclass
class InstallationResult:
    """Result of attempting installation on one device."""

    device: AndroidDevice
    status: str
    message: str = ""


def get_folders_in_downloads() -> list[Path]:
    """Return Downloads folders that contain APK files."""

    downloads_path = Path.home() / "Downloads"
    excluded_suffixes = {".app", ".download", ".bundle", ".framework"}
    folders = [
        path
        for path in downloads_path.iterdir()
        if path.is_dir()
        and path.suffix.lower() not in excluded_suffixes
        and contains_apk_files(path)
    ]
    matching_folders = [downloads_path] if contains_apk_files(downloads_path) else []
    return [*matching_folders, *folders]


def contains_apk_files(folder: Path) -> bool:
    """Return whether a folder directly contains at least one APK file."""

    return any(path.is_file() and path.suffix.lower() == ".apk" for path in folder.iterdir())


def find_matching_apk(folder: Path, device: AndroidDevice) -> Optional[Path]:
    """Return the newest APK matching a device's configured pattern."""

    matches = list(folder.glob(device.apk_name_pattern))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def build_installation_plan(folder: Path, devices: list[AndroidDevice]) -> list[InstallationPlan]:
    """Build an APK plan for every connected supported device."""

    return [
        InstallationPlan(device=device, apk_path=find_matching_apk(folder, device))
        for device in devices
    ]


def run_installation(plan: InstallationPlan, console) -> InstallationResult:
    """Uninstall, install, and configure one device's APK."""

    if plan.apk_path is None:
        return InstallationResult(plan.device, "skipped", "No matching APK found")

    device = plan.device
    console.rule(device.name)
    console.print(f"Serial: {device.serial}")
    console.print(f"APK: {plan.apk_path.name}")
    console.rule()

    uninstall_error = uninstall_application(device, console)
    if uninstall_error:
        return InstallationResult(device, "failed", uninstall_error)

    configure_install_verification(device, console)

    install_error = run_step(
        console,
        "Installing new APK...",
        "APK installed",
        ["adb", "-s", device.serial, "install", "-r", str(plan.apk_path)],
    )
    if install_error:
        return InstallationResult(device, "failed", install_error)

    permission_error = grant_permissions(device, console)
    if permission_error:
        return InstallationResult(device, "failed", permission_error)

    return InstallationResult(device, "success")


def uninstall_application(device: AndroidDevice, console) -> Optional[str]:
    """Uninstall the application if it is currently installed."""

    if not is_package_installed(device):
        console.print("[yellow]○ Application not installed — skipping uninstall[/yellow]")
        return None

    return run_step(
        console,
        "3.1 Uninstalling current application...",
        "Application uninstalled",
        [
            "adb",
            "-s",
            device.serial,
            "uninstall",
            device.package_name,
        ],
    )


def configure_install_verification(device: AndroidDevice, console) -> None:
    """Disable Android install verification before streaming the APK."""

    settings = (
        ("package_verifier_enable", "0"),
        ("verifier_verify_adb_installs", "0"),
        ("package_verifier_user_consent", "-1"),
    )

    for setting, value in settings:
        result = run_adb_command(
            [
                "adb",
                "-s",
                device.serial,
                "shell",
                "settings",
                "put",
                "global",
                setting,
                value,
            ]
        )
        if result.returncode != 0:
            console.print(f"[yellow]Warning: could not configure {setting}[/yellow]")
            print_command_output(console, result)


def run_step(console, message: str, success_message: str, command: list[str]) -> Optional[str]:
    """Run one ADB step with a worker-facing spinner and concise result."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task_id = progress.add_task(message, total=None)
        result = run_adb_command(command)
        progress.remove_task(task_id)

    if result.returncode != 0:
        print_command_failure(console, message.rstrip("."), result)
        return command_failure_reason(result)

    console.print(f"[green]✓ {success_message}[/green]")
    return None


def command_output(result) -> str:
    """Combine ADB stdout and stderr for reliable diagnostics."""

    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())


def print_command_output(console, result) -> None:
    """Print non-empty ADB output without exposing an empty error line."""

    output = command_output(result)
    if output:
        console.print(output)


def print_command_failure(console, step: str, result) -> None:
    """Print the failing step, exit code, and complete ADB diagnostics."""

    console.print(f"[red]✗ {step} failed (ADB exit code {result.returncode})[/red]")
    output = command_output(result)
    console.print(f"[red]{output or 'ADB returned no diagnostic output.'}[/red]")


def command_failure_reason(result) -> str:
    """Return the exit code and ADB output for an installation result."""

    output = command_output(result) or "ADB returned no diagnostic output."
    return f"ADB exit code {result.returncode}: {output}"


def grant_permissions(device: AndroidDevice, console) -> Optional[str]:
    """Grant the permissions configured for an installed device package."""

    if not device.permissions:
        console.print("[green]✓ Permissions granted[/green]")
        return None

    for permission in device.permissions:
        result = run_adb_command(
            [
                "adb",
                "-s",
                device.serial,
                "shell",
                "pm",
                "grant",
                device.package_name,
                permission,
            ]
        )
        if result.returncode != 0:
            console.print(f"[red]✗ Failed to grant {permission}[/red]")
            print_command_output(console, result)
            return command_failure_reason(result)

    console.print("[green]✓ Permissions granted[/green]")
    return None


def is_package_installed(device: AndroidDevice) -> bool:
    """Return whether the configured package is installed on the device."""

    result = run_adb_command(
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "pm",
            "path",
            device.package_name,
        ]
    )

    return result.returncode == 0 and bool(result.stdout.strip())


def grant_manage_all_files(device: AndroidDevice, console) -> str | None:
    """Grant Manage All Files access to the installed application."""

    return run_step(
        console,
        "3.4 Granting all files access...",
        "All files access granted",
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "appops",
            "set",
            device.package_name,
            "MANAGE_EXTERNAL_STORAGE",
            "allow",
        ],
    )
