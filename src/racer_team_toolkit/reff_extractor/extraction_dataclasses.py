from dataclasses import dataclass


@dataclass
class DeviceExtractionResult:
    """File transfer result for one Android device."""

    reff_files: int = 0
    videos: int = 0
