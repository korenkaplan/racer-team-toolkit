"""Dataclasses for IMU recordings extraction."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ImuRecording:
    """Represents one IMU recording on the remote server."""

    filename: str
    modified_at: datetime
    size: int
