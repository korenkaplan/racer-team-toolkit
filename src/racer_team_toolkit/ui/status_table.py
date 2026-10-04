"""Reusable main-thread-owned live status table for device operations."""

from rich.table import Table
from rich.text import Text


class DeviceStatusTable:
    """Keep stable device rows while individual status cells change."""

    def __init__(self, title: str, devices: dict[str, str], columns: list[str]):
        self.title = title
        self.devices = devices
        self.columns = columns
        self.rows = {serial: {column: "-" for column in columns} for serial in devices}

    def update(self, serial: str, **cells: str) -> None:
        for column, value in cells.items():
            if column not in self.columns:
                raise KeyError(column)
            self.rows[serial][column] = value

    def render(self) -> Table:
        table = Table(title=self.title, show_lines=True)
        table.add_column("Device")
        for column in self.columns:
            table.add_column(column)
        for serial, name in self.devices.items():
            table.add_row(Text(name), *(Text(self.rows[serial][c]) for c in self.columns))
        return table
