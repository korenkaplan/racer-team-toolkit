from dataclasses import dataclass
from datetime import datetime

from racer_team_toolkit.config import AndroidDevice


@dataclass
class DeviceTimeInfo:
    """Absolute and local-clock comparison information for one Android device."""

    device: AndroidDevice
    device_datetime: datetime
    difference_seconds: float
    needs_fix: bool
    absolute_difference_seconds: float
    local_difference_seconds: float
    absolute_time_needs_fix: bool
    local_time_needs_fix: bool


@dataclass
class TimeAdjustmentResult:
    """Result of correcting existing files on one Android device."""

    device: AndroidDevice
    reff_files_adjusted: int = 0
    videos_adjusted: int = 0
    success: bool = True
    error: str = ""


@dataclass
class FileTimeCorrection:
    """One remote file timestamp correction."""

    file_path: str
    current_timestamp: int
    corrected_timestamp: int
