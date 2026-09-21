"""Connected Android devices panel."""

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from racer_team_toolkit.adb.functions import (
    get_connected_android_devices,
)
from racer_team_toolkit.config import AndroidDevice


class DeviceDetectionWorker(QObject):
    """Detect Android devices without blocking the GUI."""

    finished = Signal(list)
    failed = Signal(str)

    def run(self) -> None:
        """Detect connected Android devices."""

        try:
            devices = get_connected_android_devices()
            self.finished.emit(devices)

        except Exception as error:
            self.failed.emit(str(error))


class DevicePanel(QFrame):
    """Display connected Android devices."""

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("devicePanel")

        self.thread: QThread | None = None
        self.worker: DeviceDetectionWorker | None = None

        self.device_list_layout = QVBoxLayout()

        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        """Build the connected devices panel."""

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        layout.setSpacing(14)

        header = QHBoxLayout()

        title = QLabel("Connected Devices")
        title.setObjectName("panelTitle")

        self.status_label = QLabel("Checking...")

        self.status_label.setObjectName("panelStatus")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status_label)

        layout.addLayout(header)

        layout.addLayout(self.device_list_layout)

        self.refresh_button = QPushButton("Refresh Devices")

        self.refresh_button.setObjectName("secondaryButton")

        self.refresh_button.clicked.connect(self.refresh_devices)

        layout.addWidget(self.refresh_button)

    def refresh_devices(self) -> None:
        """Refresh connected devices in a background thread."""

        if self.thread is not None and self.thread.isRunning():
            return

        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Checking...")

        self.status_label.setText("Detecting devices...")

        self.thread = QThread()
        self.worker = DeviceDetectionWorker()

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.finished.connect(self._show_devices)

        self.worker.failed.connect(self._show_error)

        self.worker.finished.connect(self.thread.quit)

        self.worker.failed.connect(self.thread.quit)

        self.thread.finished.connect(self._cleanup_thread)

        self.thread.start()

    def _show_devices(
        self,
        devices: list[AndroidDevice],
    ) -> None:
        """Display detected Android devices."""

        self._clear_device_list()

        if not devices:
            empty_label = QLabel("No supported Android devices connected.")

            empty_label.setObjectName("emptyState")

            self.device_list_layout.addWidget(empty_label)

            self.status_label.setText("0 devices")

            return

        for device in devices:
            row = self._build_device_row(device)

            self.device_list_layout.addWidget(row)

        count = len(devices)

        self.status_label.setText(f"{count} device" if count == 1 else f"{count} devices")

    def _build_device_row(
        self,
        device: AndroidDevice,
    ) -> QFrame:
        """Build one connected-device row."""

        row = QFrame()
        row.setObjectName("deviceRow")

        layout = QHBoxLayout(row)

        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        device_info = QVBoxLayout()

        name = QLabel(device.name)
        name.setObjectName("deviceName")

        serial = QLabel(f"Serial: {device.serial}")

        serial.setObjectName("deviceSerial")

        device_info.addWidget(name)
        device_info.addWidget(serial)

        status = QLabel("● Connected")
        status.setObjectName("deviceConnected")

        layout.addLayout(device_info)
        layout.addStretch()
        layout.addWidget(status)

        return row

    def _show_error(
        self,
        message: str,
    ) -> None:
        """Display device detection error."""

        self._clear_device_list()

        error_label = QLabel(f"Device detection failed: {message}")

        error_label.setWordWrap(True)
        error_label.setObjectName("errorText")

        self.device_list_layout.addWidget(error_label)

        self.status_label.setText("Detection failed")

    def _clear_device_list(self) -> None:
        """Remove all device rows."""

        while self.device_list_layout.count():
            item = self.device_list_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def _cleanup_thread(self) -> None:
        """Clean up the finished worker thread."""

        self.worker = None
        self.thread = None

        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh Devices")
