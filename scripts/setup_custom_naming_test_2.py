import os
import shlex
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from racer_team_toolkit.adb import get_adb_executable
from racer_team_toolkit.config import (
    PROJECT_STATUS,
    REFF_REMOTE_PATHS,
    VIDEO_REMOTE_PATHS,
)
from racer_team_toolkit.reff_extractor.transfer import (
    MIN_REFF_FILE_SIZE_BYTES,
    MIN_VIDEO_FILE_SIZE_BYTES,
)

DEVICE_SERIAL = "R52Y901B9AP"
SOURCE_DIRECTORY = Path("/Users/korenkaplan/Desktop/Test New Extraction Logic")


def adb(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [get_adb_executable(), "-s", DEVICE_SERIAL, *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> None:
    if PROJECT_STATUS != "development":
        raise SystemExit("Set development mode before running this test.")

    reff_source = SOURCE_DIRECTORY / "01_08_2024_08_27.reff"
    video_source = SOURCE_DIRECTORY / "full_screen_2024-08-01_08-27.mp4"

    for source, minimum_size in (
        (reff_source, MIN_REFF_FILE_SIZE_BYTES),
        (video_source, MIN_VIDEO_FILE_SIZE_BYTES),
    ):
        if not source.is_file():
            raise SystemExit(f"Missing source: {source}")

        if source.stat().st_size < minimum_size:
            raise SystemExit(f"Source below minimum size: {source}")

    adb("get-state")

    device_timestamp = int(adb("shell", "date", "+%s").stdout.strip())
    reff_timestamp = device_timestamp - 60
    video_timestamp = reff_timestamp + 20

    if datetime.fromtimestamp(reff_timestamp).date() != datetime.now().date():
        raise SystemExit("Test timestamp must be today on computer.")

    run_id = uuid.uuid4().hex[:8]
    reff_custom_name = f"Test2_Bridge_Test_{run_id}"
    video_custom_name = f"Test2_River_Test_{run_id}"

    reff_name = f"{reff_custom_name}.reff"
    video_name = f"{video_custom_name}.mp4"
    copies_directory = SOURCE_DIRECTORY / "Custom_Naming_Test_2" / run_id
    copies_directory.mkdir(parents=True, exist_ok=False)

    uploads = [
        (
            reff_source,
            copies_directory / reff_name,
            reff_timestamp,
            REFF_REMOTE_PATHS[0],
        ),
        (
            video_source,
            copies_directory / video_name,
            video_timestamp,
            VIDEO_REMOTE_PATHS[0],
        ),
    ]

    # Prepare copies first. Originals remain unchanged.
    for source, local_copy, timestamp, _ in uploads:
        shutil.copy2(source, local_copy)
        os.utime(local_copy, (timestamp, timestamp))

    for _, local_copy, timestamp, remote_directory in uploads:
        remote_file = f"{remote_directory.rstrip('/')}/{local_copy.name}"

        adb("shell", "mkdir", "-p", remote_directory)

        exists = subprocess.run(
            [
                get_adb_executable(),
                "-s",
                DEVICE_SERIAL,
                "shell",
                "test",
                "-e",
                remote_file,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if exists.returncode == 0:
            raise SystemExit(f"Remote file already exists: {remote_file}")

        adb("push", str(local_copy), remote_file)

        # Set device mtime explicitly; adb push may change it.
        adb("shell", "touch", "-m", "-d", f"@{timestamp}", remote_file)

        actual_timestamp = int(adb("shell", "stat", "-c", "%Y", remote_file).stdout.strip())

        if actual_timestamp != timestamp:
            raise SystemExit(f"Unexpected remote mtime: {remote_file}")

        print(f"Uploaded: {remote_file}")
        print(f"mtime: {datetime.fromtimestamp(timestamp)}")

    print(f"\nLocal copies: {copies_directory}")
    print("Expected behavior: conflict menu with these choices:")
    print(f"  {reff_custom_name}")
    print(f"  {video_custom_name}")
    print("Expected folder: Flight_XX_<selected name>")
    print("Original files unchanged.")


def reset_test_device_folders() -> None:
    """Clear recording files from the two configured test destinations."""

    directories = dict.fromkeys(
        [
            REFF_REMOTE_PATHS[0],
            VIDEO_REMOTE_PATHS[0],
        ]
    )

    for directory in directories:
        directory = directory.rstrip("/")

        if not directory.startswith("/sdcard/"):
            raise SystemExit(f"Refusing to reset unexpected path: {directory}")

        adb("shell", shlex.join(["mkdir", "-p", directory]))

        command = shlex.join(
            [
                "find",
                directory,
                "-type",
                "f",
                "-exec",
                "rm",
                "-f",
                "--",
                "{}",
                "+",
            ]
        )

        adb("shell", command)
        print(f"Reset device folder: {directory}")


if __name__ == "__main__":
    main()
