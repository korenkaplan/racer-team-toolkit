import shutil
import subprocess
from pathlib import Path

from racer_team_toolkit.config import AndroidDevice
from tests.integration.reff_extractor.config import (
    ISR_SERIAL,
    MANUAL_OUTPUT_ROOT,
    REAL_REMOTE_REFF_PATH,
    REAL_REMOTE_VIDEO_PATH,
    TABLET_SERIAL,
)


def run_adb(
    serial: str,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ADB against one fixed integration-test device."""

    return subprocess.run(
        [
            "adb",
            "-s",
            serial,
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
    )


def connected_serials() -> set[str]:
    """Return serials currently reported by adb devices."""

    result = subprocess.run(
        ["adb", "devices"],
        capture_output=True,
        text=True,
        check=True,
    )

    serials: set[str] = set()

    for line in result.stdout.splitlines()[1:]:
        parts = line.split()

        if len(parts) >= 2 and parts[1] == "device":
            serials.add(parts[0])

    return serials


def require_fixed_devices() -> None:
    """Fail when either fixed physical Android test device is unavailable."""

    serials = connected_serials()
    required = {
        ISR_SERIAL,
        TABLET_SERIAL,
    }
    missing = required - serials

    if missing:
        raise RuntimeError(
            "Required ADB test devices are not connected: " + ", ".join(sorted(missing))
        )


def build_test_device(
    serial: str,
    device_type: str,
) -> AndroidDevice:
    """Build a logical device that uses the real application Android paths."""

    return AndroidDevice(
        name=f"{device_type} Test Device",
        serial=serial,
        remote_log_path=REAL_REMOTE_REFF_PATH,
        file_prefix=device_type,
        apk_name_pattern="",
        package_name="",
    )


def push_file_direct(
    serial: str,
    source: Path,
    remote_path: str,
    timestamp: float,
) -> str:
    """Push a master fixture directly to its real Android path and set mtime."""

    run_adb(
        serial,
        "push",
        "-a",
        str(source),
        remote_path,
    )

    run_adb(
        serial,
        "shell",
        "touch",
        "-m",
        "-d",
        f"@{int(timestamp)}",
        remote_path,
    )

    return remote_path


def remote_file_exists(
    serial: str,
    remote_path: str,
) -> bool:
    """Return whether one exact Android path already exists."""

    return (
        run_adb(
            serial,
            "shell",
            "test",
            "-e",
            remote_path,
            check=False,
        ).returncode
        == 0
    )


def remove_remote_file(
    serial: str,
    remote_path: str,
) -> None:
    """Delete one exact test-created Android file."""

    run_adb(
        serial,
        "shell",
        "rm",
        "-f",
        remote_path,
    )


def remove_remote_files(
    serial: str,
    remote_paths: list[str],
) -> None:
    """Delete exact test-created Android files without touching unrelated files."""

    for remote_path in remote_paths:
        remove_remote_file(
            serial,
            remote_path,
        )


def ensure_real_remote_directories(
    serials: tuple[str, ...] | None = None,
) -> None:
    """Ensure the real application directories exist on selected devices."""

    target_serials = serials or (
        ISR_SERIAL,
        TABLET_SERIAL,
    )

    for serial in target_serials:
        for remote_path in (
            REAL_REMOTE_REFF_PATH,
            REAL_REMOTE_VIDEO_PATH,
        ):
            result = run_adb(
                serial,
                "shell",
                "mkdir",
                "-p",
                remote_path,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to prepare {remote_path} on {serial}: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )


def recreate_case_directory(
    case_name: str,
) -> Path:
    """Create a clean visible Desktop directory for one integration case."""

    case_dir = MANUAL_OUTPUT_ROOT / case_name

    if case_dir.exists():
        shutil.rmtree(case_dir)

    case_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return case_dir


def write_case_description(
    case_dir: Path,
    *,
    title: str,
    purpose: str,
    setup: str,
    expected: str,
) -> None:
    """Write a human-readable explanation beside every visible test result."""

    text = (
        f"TEST: {title}\n"
        f"{'=' * 72}\n\n"
        f"PURPOSE\n{purpose.strip()}\n\n"
        f"TEST SETUP\n{setup.strip()}\n\n"
        f"EXPECTED RESULT\n{expected.strip()}\n"
    )

    (case_dir / "TEST_DESCRIPTION.txt").write_text(
        text,
        encoding="utf-8",
    )


def write_actual_tree(
    case_dir: Path,
    dump_dir: Path,
) -> None:
    """Write the actual resulting dump tree for easy manual comparison."""

    lines = [
        "ACTUAL RESULT",
        "=" * 72,
        "",
    ]

    if not dump_dir.exists():
        lines.append("<dump folder does not exist>")
    else:
        lines.append(dump_dir.name + "/")

        for path in sorted(
            dump_dir.rglob("*"),
            key=lambda item: str(item.relative_to(dump_dir)),
        ):
            relative = path.relative_to(dump_dir)
            depth = len(relative.parts) - 1
            prefix = "    " * (depth + 1)
            suffix = "/" if path.is_dir() else ""
            lines.append(f"{prefix}{relative.name}{suffix}")

    (case_dir / "ACTUAL_RESULT.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_warnings(
    case_dir: Path,
    warnings: list,
) -> None:
    """Persist grouping warnings and echo them to the terminal."""

    lines = [
        "GROUPING WARNINGS",
        "=" * 72,
        "",
    ]

    if not warnings:
        lines.append("No warnings.")
        print("Warnings: none")
    else:
        print(f"Warnings: {len(warnings)}")

        for index, warning in enumerate(
            warnings,
            start=1,
        ):
            flight_name = warning.flight_name if warning.flight_name is not None else "<standalone>"

            lines.extend(
                [
                    f"Warning {index}",
                    f"Device: {warning.device_type.value}",
                    f"Video: {warning.filename}",
                    f"Flight: {flight_name}",
                    f"Message: {warning.message}",
                    "",
                ]
            )

            print(f"  [{index}] {warning.device_type.value}: {warning.message}")

    (case_dir / "WARNINGS.txt").write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )


def write_status(
    case_dir: Path,
    status: str,
    details: str = "",
) -> None:
    """Persist automated PASS/FAIL information in the visible case folder."""

    text = f"AUTOMATED RESULT: {status}\n"

    if details:
        text += f"\n{details.strip()}\n"

    (case_dir / "AUTOMATED_RESULT.txt").write_text(
        text,
        encoding="utf-8",
    )


def real_reff_path(filename: str) -> str:
    return f"{REAL_REMOTE_REFF_PATH}/{filename}"


def real_video_path(filename: str) -> str:
    return f"{REAL_REMOTE_VIDEO_PATH}/{filename}"
