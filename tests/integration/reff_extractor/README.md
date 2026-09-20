# REFF extractor integration tests

This environment now uses the real Android devices and the real application
paths for every integration case.

## Fixed physical devices

- ISR: `f7b2909c`
- Tablet: `R52Y901B9AP`

There is no separate RACER serial configured. When a test needs a logical RACER
stream, the physical Tablet is reused as the transport device and processed with
the RACER logical prefix. The files still travel through a real Android device
and the real Android filesystem paths.

## Real Android paths

- REFF: `/sdcard/Records`
- Videos: `/sdcard/Eyesatop-Records/Screen-Videos`

The tests do not use a fake remote test directory.

The tests select only the exact files created for each case when running the
transfer code, so unrelated files already on the device are not pulled into the
test result.

## Master source files

The test assets always come from:

```text
/Users/korenkaplan/Desktop/Test New Extraction Logic
```

Expected files:

- `01_08_2024_08_27.reff`
- `01_08_2024_08_28.reff`
- `ScreenRec_2024-08-01_08-27.mp4`

They are pushed directly from this folder to the Android device. There is no
local staging copy.

## Run one normal case at a time

Both Android clocks should be correct before running normal tests.

```bash
uv run python -m tests.integration.reff_extractor.manual_runner
```

Every case creates a visible Desktop folder under:

```text
~/Desktop/Reff Integration Tests/
```

Every case folder contains:

```text
TEST_DESCRIPTION.txt
ACTUAL_RESULT.txt
AUTOMATED_RESULT.txt
DUMP/
```

The description explains the test setup and expected result. `ACTUAL_RESULT.txt`
contains the actual resulting tree. The `DUMP/` folder is preserved so it can
be opened manually.

### Numbering test

Case 09 intentionally leaves this visible state before creating the next flight:

```text
1 = Flight_01
2 = Flight_02
3 = standalone REFF
4 = standalone video
5 = next created flight
```

The final visible result must contain `Flight_01`, `Flight_02`, the standalone
REFF/video, and `Flight_05`.

The case folder also contains `NUMBERING_MAP.txt`.

### Video-only flight test

Case 12 verifies the new grouping rule that a flight may be created from
multiple related videos even when no REFF exists:

```text
VIDEO 1 + VIDEO 2 -> create Flight_01
VIDEO 3 -> check existing flights first -> join Flight_01
```

The expected final folder contains all three videos, zero REFF files, and one
missing-REFF warning per video.

Video matching priority is:

```text
1. Existing flight folder
   - same-device REFF match
   - cross-device REFF match
   - video-to-video match
2. Standalone REFF
3. Standalone video
4. Remain standalone
```

## Run all normal real-device cases

```bash
RUN_REFF_INTEGRATION_TESTS=1 uv run pytest   tests/integration/reff_extractor/test_grouping_cases.py -v -s
```

## Time Adjustment tests

Time Adjustment is deliberately separate because it requires a wrong Android
clock.

Only the Tablet should be changed.

Set the Tablet manually to:

```text
Date: 2024-08-01
Time: 08:30:00
```

Then run:

```bash
uv run python -m tests.integration.reff_extractor.time_adjustment_runner
```

The Time Adjustment output is preserved under:

```text
~/Desktop/Reff Integration Tests/Time Adjustment/
```

Both Time Adjustment cases now contain their own `DUMP/` folder and
`TEST_DESCRIPTION.txt`.

Case 01 validates:

- timestamp correction
- REFF rename
- video rename
- extraction from the real Tablet paths
- the corrected flight-folder timestamp

Case 02 validates:

- video filename collision handling
- `_Number_1`
- both videos still exist
- the two related videos create one video-only flight folder
- the flight contains zero REFF files
- both videos produce missing-REFF warnings

The tests fail before setup if a generated corrected filename already exists on
the Tablet, rather than deleting or overwriting a potentially real file.

After Time Adjustment testing, restore the Tablet to automatic/current date and
time before running normal tests again.
