"""PySide6 IMU recordings extraction page."""

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from racer_team_toolkit.imu_recordings.config import IMU_REMOTE_DIRECTORY
from racer_team_toolkit.imu_recordings.dataclasses import ImuRecording
from racer_team_toolkit.imu_recordings.functions import (
    get_imu_recordings,
    get_local_imu_directory,
)
from racer_team_toolkit.ssh.functions import (
    connect_to_server,
    is_ssh_server_reachable,
)


class ImuLoadWorker(QObject):
    """Load IMU recordings from the server."""

    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Connect to the server and load available recordings."""

        ssh = None

        try:
            self.status.emit("Checking IMU server connection...")

            if not is_ssh_server_reachable():
                self.failed.emit("IMU server is not reachable.")
                return

            self.status.emit("✓ IMU server is reachable")
            self.status.emit("Connecting to IMU server...")

            ssh = connect_to_server()

            if ssh is None:
                self.failed.emit("Could not connect to IMU server.")
                return

            self.status.emit("✓ Connected to IMU server")
            self.status.emit("Loading IMU recordings...")

            recordings = get_imu_recordings(ssh)

            self.status.emit(
                f"✓ Loaded {len(recordings)} recording(s)"
            )
            self.finished.emit(recordings)

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            if ssh is not None:
                ssh.close()


class ImuDownloadWorker(QObject):
    """Download selected IMU recordings with live transfer progress."""

    status = Signal(str)
    file_progress = Signal(str, int, int)
    overall_progress = Signal(int, int)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        recordings: list[ImuRecording],
        destination: Path,
    ) -> None:
        super().__init__()
        self.recordings = recordings
        self.destination = destination

    def run(self) -> None:
        """Download all selected IMU recordings."""

        ssh = None
        copied_files: list[Path] = []
        failures: list[str] = []

        try:
            self.status.emit("Checking IMU server connection...")

            if not is_ssh_server_reachable():
                self.failed.emit("IMU server is not reachable.")
                return

            self.status.emit("Connecting to IMU server...")

            ssh = connect_to_server()

            if ssh is None:
                self.failed.emit("Could not connect to IMU server.")
                return

            self.status.emit("✓ Connected to IMU server")

            self.destination.mkdir(
                parents=True,
                exist_ok=True,
            )

            total_recordings = len(self.recordings)

            with ssh.open_sftp() as sftp:
                for index, recording in enumerate(
                    self.recordings,
                    start=1,
                ):
                    remote_path = (
                        f"{IMU_REMOTE_DIRECTORY}/{recording.filename}"
                    )
                    local_path = self.destination / recording.filename

                    self.status.emit(
                        f"Downloading {recording.filename}..."
                    )

                    try:
                        sftp.get(
                            remote_path,
                            str(local_path),
                            callback=lambda transferred, total, name=recording.filename: (
                                self.file_progress.emit(
                                    name,
                                    transferred,
                                    total,
                                )
                            ),
                        )

                        copied_files.append(local_path)
                        self.status.emit(
                            f"✓ Copied {recording.filename}"
                        )

                    except OSError as error:
                        message = (
                            f"Failed to copy {recording.filename}: {error}"
                        )
                        failures.append(message)
                        self.status.emit(f"✗ {message}")

                    self.overall_progress.emit(
                        index,
                        total_recordings,
                    )

            self.finished.emit(
                copied_files,
                failures,
            )

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            if ssh is not None:
                ssh.close()


class ImuRecordingsPage(QWidget):
    """Desktop interface for extracting IMU recordings."""

    def __init__(self) -> None:
        super().__init__()

        self.recordings: list[ImuRecording] = []
        self.recording_checkboxes: list[
            tuple[ImuRecording, QCheckBox]
        ] = []

        self.load_thread: QThread | None = None
        self.load_worker: ImuLoadWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: ImuDownloadWorker | None = None

        self.destination = get_local_imu_directory()
        self._initial_load_done = False

        self._build_ui()

    def on_activated(self) -> None:
        """Load recordings the first time this page is opened."""

        if self._initial_load_done:
            return

        self._initial_load_done = True
        self.load_recordings()

    def _build_ui(self) -> None:
        """Build the IMU extraction page."""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(16)

        title = QLabel("Extract IMU Recordings")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Browse recordings on the server and copy selected CSV files locally."
        )
        subtitle.setObjectName("pageSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(10)

        content = QHBoxLayout()
        content.setSpacing(16)

        selection_card = QFrame()
        selection_card.setObjectName("workflowCard")
        selection_layout = QVBoxLayout(selection_card)
        selection_layout.setContentsMargins(22, 20, 22, 20)
        selection_layout.setSpacing(12)

        header = QHBoxLayout()

        selection_title = QLabel("Available Recordings")
        selection_title.setObjectName("sectionTitle")

        self.recording_count = QLabel("Loading...")
        self.recording_count.setObjectName("statusPill")

        header.addWidget(selection_title)
        header.addStretch()
        header.addWidget(self.recording_count)

        self.recording_list_widget = QWidget()
        self.recording_list_layout = QVBoxLayout(
            self.recording_list_widget
        )
        self.recording_list_layout.setContentsMargins(0, 0, 0, 0)
        self.recording_list_layout.setSpacing(8)
        self.recording_list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("recordingScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.recording_list_widget)

        selection_buttons = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self.load_recordings)

        select_all_button = QPushButton("Select All")
        select_all_button.setObjectName("secondaryButton")
        select_all_button.clicked.connect(
            lambda: self._set_all_checked(True)
        )

        clear_button = QPushButton("Clear")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(
            lambda: self._set_all_checked(False)
        )

        selection_buttons.addWidget(self.refresh_button)
        selection_buttons.addWidget(select_all_button)
        selection_buttons.addWidget(clear_button)
        selection_buttons.addStretch()

        selection_layout.addLayout(header)
        selection_layout.addWidget(scroll, stretch=1)
        selection_layout.addLayout(selection_buttons)

        activity_card = QFrame()
        activity_card.setObjectName("workflowCard")
        activity_layout = QVBoxLayout(activity_card)
        activity_layout.setContentsMargins(22, 20, 22, 20)
        activity_layout.setSpacing(12)

        activity_title = QLabel("Extraction")
        activity_title.setObjectName("sectionTitle")

        self.destination_label = QLabel(
            f"Destination: {self.destination}"
        )
        self.destination_label.setObjectName("pathLabel")
        self.destination_label.setWordWrap(True)

        self.current_file_label = QLabel("Ready")
        self.current_file_label.setObjectName("mutedText")

        self.file_progress = QProgressBar()
        self.file_progress.setObjectName("operationProgress")
        self.file_progress.setRange(0, 1)
        self.file_progress.setValue(0)
        self.file_progress.setFormat("%p%")

        self.overall_progress = QProgressBar()
        self.overall_progress.setObjectName("operationProgress")
        self.overall_progress.setRange(0, 1)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("File %v of %m")

        self.log = QPlainTextEdit()
        self.log.setObjectName("installLog")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText(
            "IMU server and transfer activity will appear here..."
        )

        self.download_button = QPushButton(
            "Download Selected Recordings"
        )
        self.download_button.setObjectName("primaryButton")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(
            self.download_selected
        )

        activity_layout.addWidget(activity_title)
        activity_layout.addWidget(self.destination_label)
        activity_layout.addWidget(self.current_file_label)
        activity_layout.addWidget(self.file_progress)
        activity_layout.addWidget(self.overall_progress)
        activity_layout.addWidget(self.log, stretch=1)
        activity_layout.addWidget(self.download_button)

        content.addWidget(selection_card, stretch=1)
        content.addWidget(activity_card, stretch=1)

        root.addLayout(content, stretch=1)

    def load_recordings(self) -> None:
        """Refresh the remote recording list."""

        if self.load_thread is not None and self.load_thread.isRunning():
            return

        self.refresh_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.recording_count.setText("Loading")

        self.load_thread = QThread()
        self.load_worker = ImuLoadWorker()
        self.load_worker.moveToThread(self.load_thread)

        self.load_thread.started.connect(self.load_worker.run)
        self.load_worker.status.connect(self._append_log)
        self.load_worker.finished.connect(self._show_recordings)
        self.load_worker.failed.connect(self._show_load_error)
        self.load_worker.finished.connect(self.load_thread.quit)
        self.load_worker.failed.connect(self.load_thread.quit)
        self.load_thread.finished.connect(self._cleanup_load_thread)

        self.load_thread.start()

    def _show_recordings(
        self,
        recordings: list[ImuRecording],
    ) -> None:
        """Display remote IMU recordings."""

        self.recordings = recordings
        self.recording_checkboxes.clear()
        self._clear_recording_rows()

        for recording in recordings:
            row = QFrame()
            row.setObjectName("selectionRow")

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 11, 14, 11)

            checkbox = QCheckBox()
            checkbox.stateChanged.connect(
                self._update_download_button
            )

            details = QVBoxLayout()

            filename = QLabel(recording.filename)
            filename.setObjectName("deviceName")

            metadata = QLabel(
                f"{recording.modified_at:%d/%m/%Y %H:%M:%S}  •  "
                f"{recording.size / 1_000_000:.1f} MB"
            )
            metadata.setObjectName("deviceSerial")

            details.addWidget(filename)
            details.addWidget(metadata)

            row_layout.addWidget(checkbox)
            row_layout.addLayout(details)
            row_layout.addStretch()

            self.recording_list_layout.insertWidget(
                self.recording_list_layout.count() - 1,
                row,
            )

            self.recording_checkboxes.append(
                (recording, checkbox)
            )

        self.recording_count.setText(
            f"{len(recordings)} found"
        )

        if not recordings:
            empty = QLabel("No IMU recordings found.")
            empty.setObjectName("emptyState")
            self.recording_list_layout.insertWidget(0, empty)

        self._update_download_button()

    def _show_load_error(self, message: str) -> None:
        """Display a recording-list loading error."""

        self.recording_count.setText("Failed")
        self._append_log(f"✗ {message}")

    def _cleanup_load_thread(self) -> None:
        """Release the recording loader thread."""

        self.load_worker = None
        self.load_thread = None
        self.refresh_button.setEnabled(True)

    def _set_all_checked(self, checked: bool) -> None:
        """Select or clear all recordings."""

        for _, checkbox in self.recording_checkboxes:
            checkbox.setChecked(checked)

        self._update_download_button()

    def _update_download_button(self) -> None:
        """Enable download when at least one recording is selected."""

        selected = any(
            checkbox.isChecked()
            for _, checkbox in self.recording_checkboxes
        )

        busy = (
            self.download_thread is not None
            and self.download_thread.isRunning()
        )

        self.download_button.setEnabled(
            selected and not busy
        )

    def download_selected(self) -> None:
        """Download all checked recordings."""

        selected = [
            recording
            for recording, checkbox in self.recording_checkboxes
            if checkbox.isChecked()
        ]

        if not selected:
            return

        self.log.clear()
        self._append_log(
            f"Selected: {len(selected)} recording(s)"
        )
        self._append_log(
            f"Destination: {self.destination}"
        )

        self.file_progress.setRange(0, 1)
        self.file_progress.setValue(0)

        self.overall_progress.setRange(
            0,
            len(selected),
        )
        self.overall_progress.setValue(0)

        self.download_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        self.download_thread = QThread()
        self.download_worker = ImuDownloadWorker(
            selected,
            self.destination,
        )
        self.download_worker.moveToThread(
            self.download_thread
        )

        self.download_thread.started.connect(
            self.download_worker.run
        )
        self.download_worker.status.connect(
            self._append_log
        )
        self.download_worker.file_progress.connect(
            self._update_file_progress
        )
        self.download_worker.overall_progress.connect(
            self._update_overall_progress
        )
        self.download_worker.finished.connect(
            self._download_finished
        )
        self.download_worker.failed.connect(
            self._download_failed
        )
        self.download_worker.finished.connect(
            self.download_thread.quit
        )
        self.download_worker.failed.connect(
            self.download_thread.quit
        )
        self.download_thread.finished.connect(
            self._cleanup_download_thread
        )

        self.download_thread.start()

    def _update_file_progress(
        self,
        filename: str,
        transferred: int,
        total: int,
    ) -> None:
        """Update the current file transfer progress."""

        self.current_file_label.setText(
            f"Downloading: {filename}"
        )
        self.file_progress.setRange(0, max(total, 1))
        self.file_progress.setValue(transferred)

    def _update_overall_progress(
        self,
        completed: int,
        total: int,
    ) -> None:
        """Update selected-file progress."""

        self.overall_progress.setRange(0, max(total, 1))
        self.overall_progress.setValue(completed)

    def _download_finished(
        self,
        copied_files: list[Path],
        failures: list[str],
    ) -> None:
        """Display final extraction totals."""

        selected_count = self.overall_progress.maximum()

        self._append_log("")
        self._append_log("IMU Extraction Results")
        self._append_log(f"Selected: {selected_count}")
        self._append_log(f"Copied:   {len(copied_files)}")
        self._append_log(
            f"Failed:   {selected_count - len(copied_files)}"
        )
        self._append_log(f"Destination: {self.destination}")

        if failures:
            self._append_log("")
            for failure in failures:
                self._append_log(f"✗ {failure}")

        self.current_file_label.setText(
            "Completed" if not failures else "Completed with errors"
        )

    def _download_failed(self, message: str) -> None:
        """Display an unexpected download error."""

        self.current_file_label.setText("Failed")
        self._append_log(f"✗ {message}")

    def _cleanup_download_thread(self) -> None:
        """Release download worker references."""

        self.download_worker = None
        self.download_thread = None
        self.refresh_button.setEnabled(True)
        self._update_download_button()

    def _append_log(self, message: str) -> None:
        """Append text to the activity log."""

        self.log.appendPlainText(message)

    def _clear_recording_rows(self) -> None:
        """Delete existing recording widgets."""

        while self.recording_list_layout.count() > 1:
            item = self.recording_list_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
