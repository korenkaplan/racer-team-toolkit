from racer_team_toolkit.adb.device_detection import DeviceType
from racer_team_toolkit.config import (
    SUPPORTED_DEVICE_TYPES,
    VIDEO_FILE_PREFIX,
)


def get_device_type_from_filename(filename: str) -> DeviceType | None:
    """Return the registered device type encoded in a filename."""

    normalized_filename = filename.upper().replace(" ", "_")

    for device_type in SUPPORTED_DEVICE_TYPES:
        if normalized_filename.startswith(f"{device_type}_"):
            return DeviceType(device_type)

    return None


def get_video_device_type(
    filename: str,
) -> DeviceType | None:
    """Return the registered device type encoded in a video filename."""

    normalized_filename = filename.upper().replace(" ", "_")

    for device_type in SUPPORTED_DEVICE_TYPES:
        if normalized_filename.startswith(f"{VIDEO_FILE_PREFIX}_{device_type}"):
            return DeviceType(device_type)

    return None
