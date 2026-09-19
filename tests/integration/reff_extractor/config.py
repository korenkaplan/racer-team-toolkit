from pathlib import Path

ISR_SERIAL = "f7b2909c"
TABLET_SERIAL = "R52Y901B9AP"

SOURCE_DIR = Path("/Users/korenkaplan/Desktop/Test New Extraction Logic")
SOURCE_REFF_1 = SOURCE_DIR / "01_08_2024_08_27.reff"
SOURCE_REFF_2 = SOURCE_DIR / "01_08_2024_08_28.reff"
SOURCE_VIDEO = SOURCE_DIR / "ScreenRec_2024-08-01_08-27.mp4"

# Integration tests intentionally use the same Android paths as the real app.
REAL_REMOTE_REFF_PATH = "/sdcard/Records"
REAL_REMOTE_VIDEO_PATH = "/sdcard/Eyesatop-Records/Screen-Videos"

# Test-created files use this token whenever the filename format allows it.
TEST_FILE_TOKEN = "RTT_TEST"

RUN_ENV_VAR = "RUN_REFF_INTEGRATION_TESTS"
MANUAL_CASE_DIR_ENV_VAR = "REFF_MANUAL_CASE_DIR"

# Visible folders preserved for manual inspection.
MANUAL_OUTPUT_ROOT = Path.home() / "Desktop" / "Reff Integration Tests"

# Time Adjustment tests are intentionally separate from normal extraction tests.
# Only the Tablet clock should be intentionally wrong.
TIME_ADJUSTMENT_SERIAL = TABLET_SERIAL
TIME_ADJUSTMENT_WRONG_DATE = "2024-08-01"
TIME_ADJUSTMENT_WRONG_TIME = "08:30:00"
TIME_ADJUSTMENT_RUN_ENV_VAR = "RUN_REFF_TIME_ADJUSTMENT_TESTS"
