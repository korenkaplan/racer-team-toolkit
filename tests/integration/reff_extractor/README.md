# REFF extractor integration tests

This suite covers the grouping, priority, warning, numbering, path-update,
ADB-transfer, and time-adjustment cases discussed during manual testing.

## Fixed environment

- ISR serial: `f7b2909c`
- Tablet serial: `R52Y901B9AP`
- Master source folder:
  `/Users/korenkaplan/Desktop/Test New Extraction Logic`

Expected source files:

- `01_08_2024_08_27.reff`
- `01_08_2024_08_28.reff`
- `ScreenRec_2024-08-01_08-27.mp4`

The live tests use an isolated remote directory:

`/sdcard/racer-team-toolkit-tests`

They do not need to modify the normal production Records or Screen-Videos
directories.

## Run the complete suite

```bash
RUN_REFF_INTEGRATION_TESTS=1 uv run pytest tests/integration/reff_extractor -v
```

## Grouping and matching cases only

```bash
RUN_REFF_INTEGRATION_TESTS=1 uv run pytest   tests/integration/reff_extractor/test_grouping_cases.py -v
```

## Physical-device and time-adjustment tests only

```bash
RUN_REFF_INTEGRATION_TESTS=1 uv run pytest   tests/integration/reff_extractor/test_live_devices.py -v
```

Normal `uv run pytest` does not run these tests unless the environment variable
is explicitly enabled.
