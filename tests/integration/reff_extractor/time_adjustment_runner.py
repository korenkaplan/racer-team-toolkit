import os
import subprocess
import sys
from pathlib import Path

from tests.integration.reff_extractor.config import (
    MANUAL_OUTPUT_ROOT,
    TIME_ADJUSTMENT_RUN_ENV_VAR,
    TIME_ADJUSTMENT_SERIAL,
    TIME_ADJUSTMENT_WRONG_DATE,
    TIME_ADJUSTMENT_WRONG_TIME,
)

CASES = [
    (
        "Time Adjustment rename + flight-folder timestamp",
        "test_time_adjustment_live.py::test_time_adjustment_renaming_creates_correct_flight_folder",
    ),
    (
        "Time Adjustment filename collision (_Number_1)",
        "test_time_adjustment_live.py::test_time_adjustment_collision_uses_number_suffix",
    ),
]

TEST_ROOT = Path(__file__).parent
OUTPUT_ROOT = MANUAL_OUTPUT_ROOT / "Time Adjustment"


def print_instructions() -> None:
    print()
    print("TABLET TIME ADJUSTMENT TESTS")
    print("=" * 70)
    print(f"Tablet serial: {TIME_ADJUSTMENT_SERIAL}")
    print()
    print("Before running these tests, manually set ONLY the Tablet to:")
    print(f"  Date: {TIME_ADJUSTMENT_WRONG_DATE}")
    print(f"  Time: {TIME_ADJUSTMENT_WRONG_TIME}")
    print()
    print("Do not run the normal extraction test runner while the Tablet clock is wrong.")
    print("The tests verify the Tablet date before they start.")
    print("=" * 70)


def print_menu() -> None:
    print()

    for index, (title, _) in enumerate(
        CASES,
        start=1,
    ):
        print(f"{index}. {title}")

    print("0. Exit")


def choose_case() -> int:
    while True:
        print_menu()
        raw = input("\nSelect a time-adjustment test: ").strip()

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
    target: str,
) -> int:
    output_dir = OUTPUT_ROOT / f"Case_{case_number:02d}"

    output_dir.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    env = os.environ.copy()
    env[TIME_ADJUSTMENT_RUN_ENV_VAR] = "1"

    print()
    print("=" * 70)
    print(title)
    print(f"Visible test output: {output_dir}")
    print("=" * 70)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_ROOT / target),
            "-vv",
            "-s",
            f"--basetemp={output_dir}",
        ],
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

    return result.returncode


def main() -> None:
    print_instructions()

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

        input("\nPress Enter when you are finished inspecting this case...")


if __name__ == "__main__":
    main()
