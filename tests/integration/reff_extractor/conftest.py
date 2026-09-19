import os

import pytest

from tests.integration.reff_extractor.config import (
    ISR_SERIAL,
    RUN_ENV_VAR,
    SOURCE_REFF_1,
    SOURCE_REFF_2,
    SOURCE_VIDEO,
    TABLET_SERIAL,
    TIME_ADJUSTMENT_RUN_ENV_VAR,
)
from tests.integration.reff_extractor.helpers import connected_serials


@pytest.fixture(scope="session", autouse=True)
def require_explicit_integration_test_opt_in() -> None:
    """Keep physical-device tests out of ordinary pytest runs."""

    normal_tests_enabled = os.getenv(RUN_ENV_VAR) == "1"
    time_adjustment_enabled = os.getenv(TIME_ADJUSTMENT_RUN_ENV_VAR) == "1"

    if not normal_tests_enabled and not time_adjustment_enabled:
        pytest.skip(
            f"Set {RUN_ENV_VAR}=1 for normal REFF tests or "
            f"{TIME_ADJUSTMENT_RUN_ENV_VAR}=1 for Tablet time-adjustment tests.",
        )

    missing = [
        str(path)
        for path in (
            SOURCE_REFF_1,
            SOURCE_REFF_2,
            SOURCE_VIDEO,
        )
        if not path.is_file()
    ]

    if missing:
        pytest.fail(
            "Missing REFF integration source files:\n"
            + "\n".join(missing)
        )


@pytest.fixture(scope="session")
def connected_test_devices() -> set[str]:
    """Require the fixed ISR and Tablet physical devices."""

    serials = connected_serials()

    required = {
        ISR_SERIAL,
        TABLET_SERIAL,
    }

    missing = required - serials

    if missing:
        pytest.fail(
            "Required ADB test devices are not connected: "
            + ", ".join(sorted(missing))
        )

    return serials
