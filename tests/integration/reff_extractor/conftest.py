import os

import pytest

from tests.integration.reff_extractor.config import (
    ISR_SERIAL,
    RUN_ENV_VAR,
    SOURCE_REFF_1,
    SOURCE_REFF_2,
    SOURCE_VIDEO,
    TABLET_SERIAL,
)
from tests.integration.reff_extractor.helpers import (
    clear_remote_test_area,
    connected_serials,
)


@pytest.fixture(scope="session", autouse=True)
def require_explicit_integration_test_opt_in() -> None:
    """Keep physical-device tests out of normal pytest runs."""

    if os.getenv(RUN_ENV_VAR) != "1":
        pytest.skip(
            f"Set {RUN_ENV_VAR}=1 to run the REFF integration suite.",
        )

    required_files = [
        SOURCE_REFF_1,
        SOURCE_REFF_2,
        SOURCE_VIDEO,
    ]

    missing = [
        str(path)
        for path in required_files
        if not path.is_file()
    ]

    if missing:
        pytest.fail(
            "Missing REFF integration source files:\n"
            + "\n".join(missing)
        )


@pytest.fixture(scope="session")
def connected_test_devices() -> set[str]:
    """Require the fixed ISR and Tablet devices."""

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


@pytest.fixture
def clean_remote_test_devices(
    connected_test_devices: set[str],
):
    """Clean only the dedicated remote integration-test directories."""

    serials = [
        ISR_SERIAL,
        TABLET_SERIAL,
    ]

    for serial in serials:
        clear_remote_test_area(serial)

    yield connected_test_devices

    for serial in serials:
        clear_remote_test_area(serial)
