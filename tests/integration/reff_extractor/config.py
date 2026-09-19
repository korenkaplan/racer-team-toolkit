from pathlib import Path

ISR_SERIAL = "f7b2909c"
TABLET_SERIAL = "R52Y901B9AP"

SOURCE_DIR = Path("/Users/korenkaplan/Desktop/Test New Extraction Logic")
SOURCE_REFF_1 = SOURCE_DIR / "01_08_2024_08_27.reff"
SOURCE_REFF_2 = SOURCE_DIR / "01_08_2024_08_28.reff"
SOURCE_VIDEO = SOURCE_DIR / "ScreenRec_2024-08-01_08-27.mp4"

TEST_REMOTE_ROOT = "/sdcard/racer-team-toolkit-tests"
TEST_REMOTE_REFF_PATH = f"{TEST_REMOTE_ROOT}/Records"
TEST_REMOTE_VIDEO_PATH = f"{TEST_REMOTE_ROOT}/Screen-Videos"

RUN_ENV_VAR = "RUN_REFF_INTEGRATION_TESTS"

# Manual real-device test runner.
MANUAL_OUTPUT_ROOT = Path.home() / "Desktop" / "Reff Integration Tests"
MANUAL_REMOTE_ROOT = "/sdcard/racer-team-toolkit-manual-tests"

# Time Adjustment tests are intentionally separate from normal extraction tests.
# The Tablet is the only device whose clock should be made intentionally wrong.
TIME_ADJUSTMENT_SERIAL = TABLET_SERIAL
TIME_ADJUSTMENT_WRONG_DATE = "2024-08-01"
TIME_ADJUSTMENT_WRONG_TIME = "08:30:00"
TIME_ADJUSTMENT_REMOTE_ROOT = "/sdcard/racer-team-toolkit-time-adjustment-tests"
