"""Android device classification."""

from enum import Enum

from racer_team_toolkit.config import DEVICE_MODEL_RULES


class DeviceType(str, Enum):
    RACER = "RACER"
    ISR = "ISR"
    TABLET = "TABLET"
    BLACK_WIDOW = "BLACK_WIDOW"
    UNKNOWN = "UNKNOWN"


def normalize_model(model: str) -> str:
    """Normalize an Android model before matching."""

    return model.casefold().replace(" ", "").replace("-", "")


def classify_device(model: str) -> DeviceType:
    """Classify an Android device using configured model patterns."""

    normalized_model = normalize_model(model)

    for device_type, model_patterns in DEVICE_MODEL_RULES.items():
        if any(normalized_model.startswith(pattern) for pattern in model_patterns):
            return DeviceType(device_type)

    return DeviceType.UNKNOWN
