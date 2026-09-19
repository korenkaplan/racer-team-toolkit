from dataclasses import dataclass, field
from enum import Enum

from racer_team_toolkit.adb.device_detection import DeviceType


class FlightFileType(str, Enum):
    REFF = "REFF"
    VIDEO = "VIDEO"


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
class GroupingWarning:
    warning_type: str
    device_type: DeviceType
    filename: str
    flight_name: str | None = None
    message: str = ""


@dataclass
class GroupingResult:
    flights: list[Flight] = field(default_factory=list)
    standalone_reffs: list[FlightFile] = field(default_factory=list)
    standalone_videos: list[FlightFile] = field(default_factory=list)
    warnings: list[GroupingWarning] = field(default_factory=list)
