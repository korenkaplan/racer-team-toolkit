from dataclasses import dataclass, field
from enum import Enum

from racer_team_toolkit.adb.device_detection import DeviceType


class FlightFileType(str, Enum):
    REFF = "REFF"
    VIDEO = "VIDEO"


@dataclass
class GroupingWarning:
    """Warning created when grouping reveals an abnormal recording situation."""

    device_type: DeviceType
    filename: str
    message: str
    flight_name: str | None = None


@dataclass
class FlightFile:
    filename: str
    path: str
    device_type: DeviceType
    file_type: FlightFileType
    mtime: float
    size: int


@dataclass
class Flight:
    number: int
    name: str
    path: str
    reff_files: list[FlightFile] = field(default_factory=list)
    videos: list[FlightFile] = field(default_factory=list)


@dataclass
class GroupingResult:
    flights: list[Flight] = field(default_factory=list)
    standalone_reffs: list[FlightFile] = field(default_factory=list)
    standalone_videos: list[FlightFile] = field(default_factory=list)
    warnings: list[GroupingWarning] = field(default_factory=list)


@dataclass
class VideoGroupingResult:
    """Result of grouping videos into flights."""

    flights: list[Flight]
    warnings: list[GroupingWarning] = field(default_factory=list)


@dataclass
class ReffGroupingResult:
    flights: list[Flight]
    standalone_reffs: list[FlightFile]
    next_flight_number: int
