import os
import subprocess
import sys
from pathlib import Path

from tests.integration.reff_extractor.config import (
    MANUAL_OUTPUT_ROOT,
    RUN_ENV_VAR,
)

CASES = [
    (
        "Normal multi-device flight",
        "test_grouping_cases.py::test_case_01_normal_multi_device_flight",
    ),
    (
        "Missing-device REFF video joins existing flight",
        "test_grouping_cases.py::test_case_02_missing_device_reff_video_joins_existing_flight",
    ),
    (
        "Standalone REFF + cross-device video",
        "test_grouping_cases.py::test_case_03_cross_device_video_creates_flight_from_standalone_reff",
    ),
    (
        "Same-device standalone REFF + video",
        "test_grouping_cases.py::test_case_04_same_device_standalone_reff_and_video",
    ),
    (
        "Same-device priority beats cross-device fallback",
        "test_grouping_cases.py::test_case_05_same_device_priority_beats_cross_device_fallback",
    ),
    (
        "Priority 1 beats Priority 2",
        "test_grouping_cases.py::test_case_06_priority_one_beats_priority_two_within_same_device",
    ),
    (
        "Priority 2 when no Priority 1 exists",
        "test_grouping_cases.py::test_case_07_priority_two_used_when_no_priority_one",
    ),
    (
        "Outside 8-minute window",
        "test_grouping_cases.py::test_case_08_outside_eight_minute_window_stays_standalone",
    ),
    (
        "Repeated extraction numbering continuity",
        "test_grouping_cases.py::test_case_09_repeated_extraction_numbering_continuity",
    ),
    (
        "Closest match wins",
        "test_grouping_cases.py::test_case_10_closest_match_wins_within_same_priority",
    ),
    (
        "FlightFile path update after moves",
        "test_grouping_cases.py::test_case_11_paths_update_after_reff_and_video_move",
    ),
    (
        "LIVE ADB ISR + Tablet transfer and grouping",
        "test_live_devices.py::test_live_two_device_transfer_and_grouping",
    ),
]

TEST_ROOT = Path(__file__).parent


def slug(number: int, title: str) -> str:
    safe = "".join(
        character if character.isalnum() else "_"
        for character in title
    )

    while "__" in safe:
        safe = safe.replace("__", "_")

    return f"Case_{number:02d}_{safe.strip('_')}"


def print_menu() -> None:
    print("\nREFF Integration Test Runner")
    print("=" * 40)

    for index, (title, _) in enumerate(
        CASES,
        start=1,
    ):
        print(f"{index:2}. {title}")

    print(" 0. Exit")


def choose_case() -> int:
    while True:
        print_menu()
        raw = input("\nSelect a test: ").strip()

        try:
            choice = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue

        if 0 <= choice <= len(CASES):
            return choice

        print("Invalid selection.")


def run_case(
    case_number: int,
    title: str,
    pytest_target: str,
) -> int:
    output_dir = MANUAL_OUTPUT_ROOT / slug(
        case_number,
        title,
    )

    output_dir.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 70)
    print(f"CASE {case_number}: {title}")
    print("=" * 70)
    print(f"Visible test output: {output_dir}")
    print()

    env = os.environ.copy()
    env[RUN_ENV_VAR] = "1"

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(TEST_ROOT / pytest_target),
        "-vv",
        "-s",
        f"--basetemp={output_dir}",
    ]

    result = subprocess.run(
        command,
        env=env,
        check=False,
    )

    print()
    print("=" * 70)

    if result.returncode == 0:
        print("AUTOMATED RESULT: PASS")
    else:
        print("AUTOMATED RESULT: FAIL")

    print(f"Inspect the files here: {output_dir}")
    print("=" * 70)
    print()
    input("Press Enter when you are finished inspecting this case...")

    return result.returncode


def main() -> None:
    MANUAL_OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    while True:
        choice = choose_case()

        if choice == 0:
            return

        title, target = CASES[choice - 1]

        run_case(
            choice,
            title,
            target,
        )


if __name__ == "__main__":
    main()
