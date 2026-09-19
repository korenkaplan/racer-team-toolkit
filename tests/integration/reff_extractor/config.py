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
