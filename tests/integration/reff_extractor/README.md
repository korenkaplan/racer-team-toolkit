# REFF extractor integration tests

This test environment is split into two completely separate flows:

1. normal extraction/grouping tests with correct Android clocks
2. Tablet-only Time Adjustment tests with an intentionally wrong Tablet clock

Do not run them at the same time.

## Fixed environment

- ISR serial: `f7b2909c`
- Tablet serial: `R52Y901B9AP`
- Master source folder:
  `/Users/korenkaplan/Desktop/Test New Extraction Logic`

Expected source files:

- `01_08_2024_08_27.reff`
- `01_08_2024_08_28.reff`
- `ScreenRec_2024-08-01_08-27.mp4`

Test ADB data uses isolated directories under `/sdcard/racer-team-toolkit-tests`.
The suite does not need to clear the normal production Records or Screen-Videos
directories.

## Normal tests

The ISR and Tablet clocks should both be correct.

Run all normal automated tests:

```bash
RUN_REFF_INTEGRATION_TESTS=1 uv run pytest   tests/integration/reff_extractor/test_grouping_cases.py   tests/integration/reff_extractor/test_live_devices.py -v
```

Run cases one by one and preserve their visible Desktop output:

```bash
uv run python -m tests.integration.reff_extractor.manual_runner
```

Desktop results are stored under:

```text
~/Desktop/Reff Integration Tests/
```

## Time Adjustment tests

These tests are separate because they require an intentionally wrong Android
clock.

Only the Tablet is used for the wrong-clock tests.

Fixed test clock:

```text
Device: R52Y901B9AP
Date:   2024-08-01
Time:   08:30:00
```

Set the Tablet date/time manually before starting. The test verifies the date
before making any file corrections.

Run the Time Adjustment menu:

```bash
uv run python -m tests.integration.reff_extractor.time_adjustment_runner
```

Or run the Time Adjustment pytest file directly:

```bash
RUN_REFF_TIME_ADJUSTMENT_TESTS=1 uv run pytest   tests/integration/reff_extractor/test_time_adjustment_live.py -v
```

The Time Adjustment tests cover:

- REFF filename correction
- video filename correction
- corrected modification timestamps
- resulting flight-folder timestamp
- filename collision handling using `_Number_1`

After the Time Adjustment tests, manually restore the Tablet to automatic/current
date and time before running the normal extraction tests again.
