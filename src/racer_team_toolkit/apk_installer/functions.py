"""Reusable APK installer operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

from racer_team_toolkit.adb.functions import run_adb_command
from racer_team_toolkit.config import AndroidDevice

StatusCallback = Callable[[str], None] | None


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


def _emit_status(
    callback: StatusCallback,
    message: str,
) -> None:
    """Send a human-readable status update when a callback is provided."""

    if callback is not None:
        callback(message)


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


def run_installation(
    plan: InstallationPlan,
    console,
    *,
    status_callback: StatusCallback = None,
) -> InstallationResult:
    """Uninstall, install, and configure one device's APK."""

    if plan.apk_path is None:
        _emit_status(
            status_callback,
            f"⚠ {plan.device.name}: No matching APK found.",
        )
        return InstallationResult(plan.device, "skipped", "No matching APK found")

    device = plan.device

    console.rule(device.name)
    console.print(f"Serial: {device.serial}")
    console.print(f"APK: {plan.apk_path.name}")
    console.rule()

    _emit_status(status_callback, f"▶ {device.name}")
    _emit_status(status_callback, f"Serial: {device.serial}")
    _emit_status(status_callback, f"APK: {plan.apk_path.name}")

    uninstall_error = uninstall_application(
        device,
        console,
        status_callback=status_callback,
    )
    if uninstall_error:
        return InstallationResult(device, "failed", uninstall_error)

    configure_install_verification(
        device,
        console,
        status_callback=status_callback,
    )

    install_error = run_step(
        console,
        "Installing new APK...",
        "APK installed",
        ["-s", device.serial, "install", "-r", str(plan.apk_path)],
        status_callback=status_callback,
    )
    if install_error:
        return InstallationResult(device, "failed", install_error)

    permission_error = grant_permissions(
        device,
        console,
        status_callback=status_callback,
    )
    if permission_error:
        return InstallationResult(device, "failed", permission_error)

    _emit_status(
        status_callback,
        f"✓ {device.name} installation completed.",
    )

    return InstallationResult(device, "success")


def uninstall_application(
    device: AndroidDevice,
    console,
    *,
    status_callback: StatusCallback = None,
) -> Optional[str]:
    """Uninstall the application if it is currently installed."""

    _emit_status(
        status_callback,
        "Checking whether the current application is installed...",
    )

    if not is_package_installed(device):
        message = "Application not installed — skipping uninstall"
        console.print(f"[yellow]○ {message}[/yellow]")
        _emit_status(status_callback, f"○ {message}")
        return None

    return run_step(
        console,
        "Uninstalling current application...",
        "Application uninstalled",
        [
            "-s",
            device.serial,
            "uninstall",
            device.package_name,
        ],
        status_callback=status_callback,
    )


def configure_install_verification(
    device: AndroidDevice,
    console,
    *,
    status_callback: StatusCallback = None,
) -> None:
    """Disable Android install verification before streaming the APK."""

    _emit_status(
        status_callback,
        "Configuring Android install verification...",
    )

    settings = (
        ("package_verifier_enable", "0"),
        ("verifier_verify_adb_installs", "0"),
        ("package_verifier_user_consent", "-1"),
    )

    had_warning = False

    for setting, value in settings:
        result = run_adb_command(
            [
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
            had_warning = True
            message = f"Warning: could not configure {setting}"
            console.print(f"[yellow]{message}[/yellow]")
            _emit_status(status_callback, f"⚠ {message}")
            print_command_output(console, result)

    if had_warning:
        _emit_status(
            status_callback,
            "⚠ Install verification configured with warnings.",
        )
    else:
        _emit_status(
            status_callback,
            "✓ Install verification configured.",
        )


def run_step(
    console,
    message: str,
    success_message: str,
    command: list[str],
    *,
    status_callback: StatusCallback = None,
) -> Optional[str]:
    """Run one ADB step with a worker-facing spinner and concise result."""

    _emit_status(
        status_callback,
        message.rstrip("."),
    )

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
        reason = command_failure_reason(result)
        _emit_status(
            status_callback,
            f"✗ {message.rstrip('.')} failed: {reason}",
        )
        return reason

    console.print(f"[green]✓ {success_message}[/green]")
    _emit_status(
        status_callback,
        f"✓ {success_message}",
    )
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


def grant_permissions(
    device: AndroidDevice,
    console,
    *,
    status_callback: StatusCallback = None,
) -> Optional[str]:
    """Grant the permissions configured for an installed device package."""

    _emit_status(
        status_callback,
        "Granting application permissions...",
    )

    if not device.permissions:
        console.print("[green]✓ Permissions granted[/green]")
        _emit_status(status_callback, "✓ Permissions granted")
        return None

    for permission in device.permissions:
        _emit_status(
            status_callback,
            f"Granting {permission}...",
        )

        result = run_adb_command(
            [
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
            reason = command_failure_reason(result)
            _emit_status(
                status_callback,
                f"✗ Failed to grant {permission}: {reason}",
            )
            return reason

    console.print("[green]✓ Permissions granted[/green]")
    _emit_status(status_callback, "✓ Permissions granted")
    return None


def is_package_installed(device: AndroidDevice) -> bool:
    """Return whether the configured package is installed on the device."""

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "pm",
            "path",
            device.package_name,
        ]
    )

    return result.returncode == 0 and bool(result.stdout.strip())


def grant_manage_all_files(
    device: AndroidDevice,
    console,
    *,
    status_callback: StatusCallback = None,
) -> str | None:
    """Grant Manage All Files access to the installed application."""

    return run_step(
        console,
        "Granting all files access...",
        "All files access granted",
        [
            "-s",
            device.serial,
            "shell",
            "appops",
            "set",
            device.package_name,
            "MANAGE_EXTERNAL_STORAGE",
            "allow",
        ],
        status_callback=status_callback,
    )
