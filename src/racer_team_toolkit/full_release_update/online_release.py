"""Online release update operations."""

import socket


def is_internet_available(
    timeout: float = 3.0,
) -> bool:
    """Return whether the internet is available."""

    try:
        with socket.create_connection(
            ("drive.google.com", 443),
            timeout=timeout,
        ):
            return True

    except OSError:
        return False
