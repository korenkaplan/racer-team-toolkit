"""PySide6 JAR Management page."""

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from racer_team_toolkit.jar_management.config import (
    CAMERA_MODE_RTSP,
    CAMERA_MODE_SHARPEYE,
)
from racer_team_toolkit.jar_management.functions import (
    run_java_script,
    set_camera_mode,
    stop_screen_sessions,
    upload_jar_file,
    verify_groundlord_started,
    verify_screen_stopped,
)
from racer_team_toolkit.ssh.config import SSH_HOST, SSH_PORT
from racer_team_toolkit.ssh.functions import (
    connect_to_server,
    is_ssh_server_reachable,
)


class JarOperationWorker(QObject):
    """Run JAR operations away from the GUI thread."""

    status = Signal(str)
    transfer_progress = Signal(int, int)
    finished = Signal(bool, str)

    def __init__(
        self,
        operation: str,
        jar_path: Path | None = None,
        camera_mode: str | None = None,
    ) -> None:
        super().__init__()
        self.operation = operation
        self.jar_path = jar_path
        self.camera_mode = camera_mode

    def run(self) -> None:
        """Run the selected JAR operation."""

        ssh = None

        try:
            self.status.emit(f"Checking server connection at {SSH_HOST}:{SSH_PORT}...")

            if not is_ssh_server_reachable():
                self.finished.emit(
                    False,
                    f"SSH server is not reachable at {SSH_HOST}:{SSH_PORT}.",
                )
                return

            self.status.emit("✓ Server reachable")
            self.status.emit("Connecting to server...")

            ssh = connect_to_server()

            if ssh is None:
                self.finished.emit(
                    False,
                    "Could not connect to the server.",
                )
                return

            self.status.emit("✓ Connected to server")

            if self.operation == "camera":
                if self.camera_mode is None:
                    self.finished.emit(
                        False,
                        "No camera mode was selected.",
                    )
                    return

                self.status.emit(f"Setting camera source to {self.camera_mode}...")

                success, message = set_camera_mode(
                    ssh,
                    self.camera_mode,
                )

                if not success:
                    self.finished.emit(
                        False,
                        f"Failed to update camera source: {message}",
                    )
                    return

                self.status.emit(f"✓ {message}")

            self.status.emit("Stopping running JAR processes...")

            if not stop_screen_sessions(ssh):
                self.finished.emit(
                    False,
                    "Failed to stop existing screen sessions.",
                )
                return

            if not verify_screen_stopped(ssh):
                self.finished.emit(
                    False,
                    "Could not verify that existing screen sessions stopped.",
                )
                return

            self.status.emit("✓ Existing processes stopped")

            if self.operation == "upload":
                if self.jar_path is None or not self.jar_path.is_file():
                    self.finished.emit(
                        False,
                        "Selected JAR file does not exist.",
                    )
                    return

                self.status.emit(f"Selected: {self.jar_path}")
                self.status.emit("Uploading racer-groundlord.jar...")

                if not upload_jar_file(
                    ssh,
                    self.jar_path,
                    progress_callback=self.transfer_progress.emit,
                ):
                    self.finished.emit(
                        False,
                        "Failed to upload Racer Groundlord JAR.",
                    )
                    return

                self.status.emit("✓ JAR upload completed")

            self.status.emit("Starting Java processes...")

            success, java_output = run_java_script(ssh)

            if java_output:
                self.status.emit(java_output)

            if not success:
                self.finished.emit(
                    False,
                    "Failed to start Java processes.",
                )
                return

            self.status.emit("✓ Java startup command completed")
            self.status.emit("Verifying Racer Groundlord...")

            if not verify_groundlord_started(ssh):
                self.finished.emit(
                    False,
                    "Racer Groundlord did not start successfully.",
                )
                return

            self.status.emit("✓ Racer Groundlord is running")

            if self.operation == "upload":
                self.finished.emit(
                    True,
                    "Racer Groundlord JAR uploaded and restarted successfully.",
                )
            elif self.operation == "camera":
                self.finished.emit(
                    True,
                    f"Camera source changed to {self.camera_mode} and Racer Groundlord restarted.",
                )
            else:
                self.finished.emit(
                    True,
                    "Racer Groundlord restarted successfully.",
                )

        except Exception as error:
            self.finished.emit(
                False,
                f"Unexpected JAR operation error: {error}",
            )

        finally:
            if ssh is not None:
                ssh.close()


class JarManagementPage(QWidget):
    """Desktop interface for JAR upload and restart operations."""

    def __init__(self) -> None:
        super().__init__()

        self.selected_jar: Path | None = None
        self.thread: QThread | None = None
        self.worker: JarOperationWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the JAR Management page."""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(16)

        title = QLabel("JAR Management")
        title.setObjectName("pageTitle")

        subtitle = QLabel("Upload Racer Groundlord or restart the currently deployed JAR.")
        subtitle.setObjectName("pageSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(16)

        restart_card = self._build_restart_card()
        upload_card = self._build_upload_card()
        camera_card = self._build_camera_card()

        actions.addWidget(restart_card)
        actions.addWidget(upload_card)
        actions.addWidget(camera_card)

        root.addLayout(actions)

        activity_card = QFrame()
        activity_card.setObjectName("workflowCard")

        activity_layout = QVBoxLayout(activity_card)
        activity_layout.setContentsMargins(22, 20, 22, 20)
        activity_layout.setSpacing(12)

        activity_header = QHBoxLayout()

        activity_title = QLabel("Activity")
        activity_title.setObjectName("sectionTitle")

        self.operation_status = QLabel("Ready")
        self.operation_status.setObjectName("statusPill")

        activity_header.addWidget(activity_title)
        activity_header.addStretch()
        activity_header.addWidget(self.operation_status)

        self.progress = QProgressBar()
        self.progress.setObjectName("operationProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)

        self.log = QPlainTextEdit()
        self.log.setObjectName("installLog")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Server and JAR activity will appear here...")

        activity_layout.addLayout(activity_header)
        activity_layout.addWidget(self.progress)
        activity_layout.addWidget(self.log)

        root.addWidget(activity_card, stretch=1)

    def _build_restart_card(self) -> QFrame:
        """Build the restart action card."""

        card = QFrame()
        card.setObjectName("actionCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Restart JAR")
        title.setObjectName("sectionTitle")

        description = QLabel(
            "Stop the current screen sessions, start Java again, "
            "and verify racer-groundlord.jar is running."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        self.restart_button = QPushButton("Restart Racer Groundlord")
        self.restart_button.setObjectName("primaryButton")
        self.restart_button.clicked.connect(lambda: self._start_operation("restart"))

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        layout.addWidget(self.restart_button)

        return card

    def _build_upload_card(self) -> QFrame:
        """Build the upload action card."""

        card = QFrame()
        card.setObjectName("actionCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Upload New JAR")
        title.setObjectName("sectionTitle")

        description = QLabel(
            "Choose racer-groundlord.jar, upload it to the server, "
            "restart Java, and verify the process."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        self.jar_path_label = QLabel("No JAR selected")
        self.jar_path_label.setObjectName("pathLabel")
        self.jar_path_label.setWordWrap(True)

        choose_button = QPushButton("Choose JAR...")
        choose_button.setObjectName("secondaryButton")
        choose_button.clicked.connect(self._choose_jar)

        self.upload_button = QPushButton("Upload & Restart")
        self.upload_button.setObjectName("primaryButton")
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(lambda: self._start_operation("upload"))

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.jar_path_label)
        layout.addWidget(choose_button)
        layout.addStretch()
        layout.addWidget(self.upload_button)

        return card

    def _build_camera_card(self) -> QFrame:
        """Build the camera source selection card."""

        card = QFrame()
        card.setObjectName("actionCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Camera Source")
        title.setObjectName("sectionTitle")

        description = QLabel(
            "Choose the Racer camera startup mode. "
            "The run_java.sh configuration will be updated and Racer Groundlord restarted."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        self.sharpeye_button = QPushButton(CAMERA_MODE_SHARPEYE)
        self.sharpeye_button.setObjectName("primaryButton")
        self.sharpeye_button.clicked.connect(
            lambda: self._start_operation(
                "camera",
                CAMERA_MODE_SHARPEYE,
            )
        )

        self.rtsp_button = QPushButton(CAMERA_MODE_RTSP)
        self.rtsp_button.setObjectName("secondaryButton")
        self.rtsp_button.clicked.connect(
            lambda: self._start_operation(
                "camera",
                CAMERA_MODE_RTSP,
            )
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        layout.addWidget(self.sharpeye_button)
        layout.addWidget(self.rtsp_button)

        return card

    def _choose_jar(self) -> None:
        """Choose racer-groundlord.jar from the local computer."""

        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Racer Groundlord JAR",
            str(Path.home() / "Downloads"),
            "JAR Files (*.jar)",
        )

        if not selected:
            return

        jar_path = Path(selected)

        if jar_path.name != "racer-groundlord.jar":
            self.jar_path_label.setText("Selected file must be named racer-groundlord.jar")
            self.jar_path_label.setObjectName("errorText")
            self.jar_path_label.style().unpolish(self.jar_path_label)
            self.jar_path_label.style().polish(self.jar_path_label)
            self.selected_jar = None
            self.upload_button.setEnabled(False)
            return

        self.selected_jar = jar_path
        self.jar_path_label.setObjectName("pathLabel")
        self.jar_path_label.setText(str(jar_path))
        self.jar_path_label.style().unpolish(self.jar_path_label)
        self.jar_path_label.style().polish(self.jar_path_label)
        self.upload_button.setEnabled(True)

    def _start_operation(
        self,
        operation: str,
        camera_mode: str | None = None,
    ) -> None:
        """Start a JAR operation in a worker thread."""

        if self.thread is not None and self.thread.isRunning():
            return

        jar_path = self.selected_jar if operation == "upload" else None

        self.log.clear()
        if operation == "upload":
            start_message = "Starting JAR upload..."
        elif operation == "camera":
            start_message = f"Changing camera source to {camera_mode}..."
        else:
            start_message = "Starting Racer Groundlord restart..."

        self._append_log(start_message)

        self.operation_status.setText("Running")
        self.progress.setRange(0, 0)

        self.restart_button.setEnabled(False)
        self.upload_button.setEnabled(False)
        self.sharpeye_button.setEnabled(False)
        self.rtsp_button.setEnabled(False)

        self.thread = QThread()
        self.worker = JarOperationWorker(
            operation,
            jar_path,
            camera_mode,
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self._append_log)
        self.worker.transfer_progress.connect(self._update_transfer_progress)
        self.worker.finished.connect(self._operation_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)

        self.thread.start()

    def _append_log(self, message: str) -> None:
        """Append an operation message to the activity panel."""

        self.log.appendPlainText(message)

    def _update_transfer_progress(
        self,
        transferred: int,
        total: int,
    ) -> None:
        """Update live JAR upload progress."""

        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(transferred)

        if total > 0:
            percent = int((transferred / total) * 100)
            self.operation_status.setText(f"Uploading {percent}%")

    def _operation_finished(
        self,
        success: bool,
        message: str,
    ) -> None:
        """Display the final JAR operation result."""

        self._append_log("")
        self._append_log(f"✓ {message}" if success else f"✗ {message}")

        self.operation_status.setText("Completed" if success else "Failed")

        self.progress.setRange(0, 1)
        self.progress.setValue(1 if success else 0)

    def _cleanup_thread(self) -> None:
        """Release the operation thread."""

        self.worker = None
        self.thread = None

        self.restart_button.setEnabled(True)
        self.upload_button.setEnabled(self.selected_jar is not None)
        self.sharpeye_button.setEnabled(True)
        self.rtsp_button.setEnabled(True)
