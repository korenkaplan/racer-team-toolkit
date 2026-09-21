"""PySide6 Full Release Update page."""

import io
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from rich.console import Console

from racer_team_toolkit.adb.functions import get_connected_android_devices
from racer_team_toolkit.apk_installer.functions import (
    InstallationResult,
    run_installation,
)
from racer_team_toolkit.full_release_update.dataclasses import (
    ReleaseUpdatePlan,
)
from racer_team_toolkit.full_release_update.functions import (
    build_release_update_plan,
    change_apk_folder,
    change_jar_file,
    get_release_folders,
    skip_apk_install,
    skip_jar_upload,
)
from racer_team_toolkit.jar_management.functions import (
    run_java_script,
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


class ReleaseLoadWorker(QObject):
    """Detect devices and local release folders."""

    status = Signal(str)
    finished = Signal(object, object)
    failed = Signal(str)

    def run(self) -> None:
        """Load connected devices and release folders."""

        try:
            self.status.emit("Checking connected Android devices...")
            devices = get_connected_android_devices()

            if devices:
                self.status.emit(
                    f"✓ Connected devices: {len(devices)}"
                )
                for device in devices:
                    self.status.emit(
                        f"  {device.name} (Serial: {device.serial})"
                    )
            else:
                self.status.emit(
                    "No supported Android devices are connected."
                )

            self.status.emit(
                "Scanning Downloads for release folders..."
            )
            folders = get_release_folders()
            self.status.emit(
                f"✓ Found {len(folders)} release location(s)"
            )

            self.finished.emit(
                devices,
                folders,
            )

        except Exception as error:
            self.failed.emit(str(error))


class ReleaseExecutionWorker(QObject):
    """Execute APK updates followed by the JAR update."""

    status = Signal(str)
    progress = Signal(int, int)
    finished = Signal(object, object, bool)
    failed = Signal(str)

    def __init__(
        self,
        plan: ReleaseUpdatePlan,
    ) -> None:
        super().__init__()
        self.plan = plan

    def run(self) -> None:
        """Run the complete release plan."""

        quiet_console = Console(
            file=io.StringIO(),
            force_terminal=False,
        )
        apk_results: list[InstallationResult] = []
        jar_result: bool | None = None
        jar_blocked = False

        try:
            enabled_apks = (
                len(self.plan.apk_plan)
                if self.plan.install_apk
                else 0
            )
            total_steps = enabled_apks + (
                1 if self.plan.upload_jar else 0
            )
            completed = 0

            self.status.emit("APK Updates")

            if not self.plan.install_apk:
                self.status.emit(
                    "APK updates: SKIPPED"
                )
            else:
                for item in self.plan.apk_plan:
                    self.status.emit("")
                    self.status.emit(
                        f"▶ APK target: {item.device.name}"
                    )

                    result = run_installation(
                        item,
                        quiet_console,
                        status_callback=self.status.emit,
                    )
                    apk_results.append(result)

                    completed += 1
                    self.progress.emit(
                        completed,
                        max(total_steps, 1),
                    )

            apk_failed = any(
                result.status == "failed"
                for result in apk_results
            )

            jar_blocked = (
                apk_failed and self.plan.upload_jar
            )

            self.status.emit("")
            self.status.emit("JAR Update")

            if jar_blocked:
                self.status.emit(
                    "✗ One or more APK installations failed."
                )
                self.status.emit(
                    "JAR upload was not started because "
                    "the APK update did not complete successfully."
                )

            elif not self.plan.upload_jar:
                self.status.emit("JAR update: SKIPPED")

            elif self.plan.jar_file is None:
                self.status.emit(
                    "✗ JAR file was not selected."
                )
                jar_result = False

            else:
                jar_result = self._run_jar_update(
                    self.plan.jar_file
                )

                completed += 1
                self.progress.emit(
                    completed,
                    max(total_steps, 1),
                )

            self.finished.emit(
                apk_results,
                jar_result,
                jar_blocked,
            )

        except Exception as error:
            self.failed.emit(str(error))

    def _run_jar_update(
        self,
        jar_path: Path,
    ) -> bool:
        """Upload and restart Racer Groundlord with live GUI status."""

        ssh = None

        try:
            self.status.emit(
                f"Checking server connection at {SSH_HOST}:{SSH_PORT}..."
            )

            if not is_ssh_server_reachable():
                self.status.emit(
                    "✗ SSH server is not reachable."
                )
                return False

            self.status.emit("✓ Server reachable")
            self.status.emit("Connecting to server...")

            ssh = connect_to_server()

            if ssh is None:
                self.status.emit(
                    "✗ Could not connect to server."
                )
                return False

            self.status.emit("✓ Connected to server")
            self.status.emit(
                "Stopping running JAR processes..."
            )

            if not stop_screen_sessions(ssh):
                self.status.emit(
                    "✗ Failed to stop screen sessions."
                )
                return False

            if not verify_screen_stopped(ssh):
                self.status.emit(
                    "✗ Could not verify screen sessions stopped."
                )
                return False

            self.status.emit(
                "✓ Existing processes stopped"
            )
            self.status.emit(
                f"Selected: {jar_path}"
            )
            self.status.emit(
                "Uploading racer-groundlord.jar..."
            )

            if not upload_jar_file(
                ssh,
                jar_path,
            ):
                self.status.emit(
                    "✗ JAR upload failed."
                )
                return False

            self.status.emit("✓ JAR upload completed")
            self.status.emit("Starting Java processes...")

            success, output = run_java_script(ssh)

            if output:
                self.status.emit(output)

            if not success:
                self.status.emit(
                    "✗ Java startup command failed."
                )
                return False

            self.status.emit(
                "✓ Java startup command completed"
            )
            self.status.emit(
                "Verifying Racer Groundlord..."
            )

            if not verify_groundlord_started(ssh):
                self.status.emit(
                    "✗ Racer Groundlord did not start successfully."
                )
                return False

            self.status.emit(
                "✓ Racer Groundlord is running"
            )
            return True

        finally:
            if ssh is not None:
                ssh.close()


class FullReleasePage(QWidget):
    """Desktop full release update workflow."""

    def __init__(self) -> None:
        super().__init__()

        self.devices = []
        self.release_folders: list[Path] = []
        self.plan: ReleaseUpdatePlan | None = None

        self.load_thread: QThread | None = None
        self.load_worker: ReleaseLoadWorker | None = None
        self.execution_thread: QThread | None = None
        self.execution_worker: ReleaseExecutionWorker | None = None

        self._build_ui()
        self.refresh_sources()

    def _build_ui(self) -> None:
        """Build the full release update page."""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(16)

        title = QLabel("Full Release Update")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Prepare APK updates and Racer Groundlord from one release, "
            "review every action, then deploy."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(8)

        source_card = QFrame()
        source_card.setObjectName("workflowCard")

        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(22, 20, 22, 20)
        source_layout.setSpacing(12)

        source_header = QHBoxLayout()

        source_title = QLabel("Release Source")
        source_title.setObjectName("sectionTitle")

        self.source_status = QLabel("Loading...")
        self.source_status.setObjectName("statusPill")

        source_header.addWidget(source_title)
        source_header.addStretch()
        source_header.addWidget(self.source_status)

        self.release_combo = QComboBox()
        self.release_combo.setObjectName("folderCombo")
        self.release_combo.currentIndexChanged.connect(
            self._source_changed
        )

        source_buttons = QHBoxLayout()

        browse_release = QPushButton(
            "Browse Release Folder..."
        )
        browse_release.setObjectName("secondaryButton")
        browse_release.clicked.connect(
            self._browse_release_folder
        )

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(
            self.refresh_sources
        )

        self.build_plan_button = QPushButton(
            "Build Release Plan"
        )
        self.build_plan_button.setObjectName("primaryButton")
        self.build_plan_button.setEnabled(False)
        self.build_plan_button.clicked.connect(
            self.build_plan
        )

        source_buttons.addWidget(browse_release)
        source_buttons.addWidget(self.refresh_button)
        source_buttons.addStretch()
        source_buttons.addWidget(self.build_plan_button)

        source_layout.addLayout(source_header)
        source_layout.addWidget(self.release_combo)
        source_layout.addLayout(source_buttons)

        root.addWidget(source_card)

        center = QHBoxLayout()
        center.setSpacing(16)

        plan_card = QFrame()
        plan_card.setObjectName("workflowCard")
        plan_layout = QVBoxLayout(plan_card)
        plan_layout.setContentsMargins(22, 20, 22, 20)
        plan_layout.setSpacing(12)

        plan_title = QLabel("Release Plan")
        plan_title.setObjectName("sectionTitle")

        self.plan_table = QTableWidget()
        self.plan_table.setObjectName("dataTable")
        self.plan_table.setColumnCount(4)
        self.plan_table.setHorizontalHeaderLabels(
            [
                "Component",
                "Target",
                "File",
                "Action",
            ]
        )
        self.plan_table.horizontalHeader().setStretchLastSection(
            True
        )
        self.plan_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.plan_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )

        options = QHBoxLayout()

        self.skip_apks_checkbox = QCheckBox(
            "Skip all APK updates"
        )
        self.skip_apks_checkbox.stateChanged.connect(
            self._plan_option_changed
        )

        self.skip_jar_checkbox = QCheckBox(
            "Skip JAR upload"
        )
        self.skip_jar_checkbox.stateChanged.connect(
            self._plan_option_changed
        )

        options.addWidget(self.skip_apks_checkbox)
        options.addWidget(self.skip_jar_checkbox)
        options.addStretch()

        replacement_buttons = QHBoxLayout()

        choose_apk_folder = QPushButton(
            "Choose Different APK Folder..."
        )
        choose_apk_folder.setObjectName("secondaryButton")
        choose_apk_folder.clicked.connect(
            self._choose_apk_folder
        )

        choose_jar = QPushButton(
            "Choose Different JAR..."
        )
        choose_jar.setObjectName("secondaryButton")
        choose_jar.clicked.connect(
            self._choose_jar
        )

        replacement_buttons.addWidget(
            choose_apk_folder
        )
        replacement_buttons.addWidget(choose_jar)
        replacement_buttons.addStretch()

        plan_layout.addWidget(plan_title)
        plan_layout.addWidget(
            self.plan_table,
            stretch=1,
        )
        plan_layout.addLayout(options)
        plan_layout.addLayout(replacement_buttons)

        activity_card = QFrame()
        activity_card.setObjectName("workflowCard")
        activity_layout = QVBoxLayout(activity_card)
        activity_layout.setContentsMargins(22, 20, 22, 20)
        activity_layout.setSpacing(12)

        activity_header = QHBoxLayout()

        activity_title = QLabel("Deployment Activity")
        activity_title.setObjectName("sectionTitle")

        self.activity_status = QLabel("Ready")
        self.activity_status.setObjectName("statusPill")

        activity_header.addWidget(activity_title)
        activity_header.addStretch()
        activity_header.addWidget(self.activity_status)

        self.progress = QProgressBar()
        self.progress.setObjectName("operationProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Step %v of %m")

        self.log = QPlainTextEdit()
        self.log.setObjectName("installLog")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText(
            "Full release update activity will appear here..."
        )

        self.run_button = QPushButton(
            "Run Full Release Update"
        )
        self.run_button.setObjectName("primaryButton")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(
            self.run_release
        )

        activity_layout.addLayout(activity_header)
        activity_layout.addWidget(self.progress)
        activity_layout.addWidget(
            self.log,
            stretch=1,
        )
        activity_layout.addWidget(self.run_button)

        center.addWidget(plan_card, stretch=3)
        center.addWidget(activity_card, stretch=2)

        root.addLayout(center, stretch=1)

    def refresh_sources(self) -> None:
        """Refresh connected devices and release folders."""

        if self.load_thread is not None and self.load_thread.isRunning():
            return

        self.refresh_button.setEnabled(False)
        self.build_plan_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.source_status.setText("Loading")
        self.log.clear()

        self.load_thread = QThread()
        self.load_worker = ReleaseLoadWorker()
        self.load_worker.moveToThread(
            self.load_thread
        )

        self.load_thread.started.connect(
            self.load_worker.run
        )
        self.load_worker.status.connect(
            self._append_log
        )
        self.load_worker.finished.connect(
            self._show_sources
        )
        self.load_worker.failed.connect(
            self._load_failed
        )
        self.load_worker.finished.connect(
            self.load_thread.quit
        )
        self.load_worker.failed.connect(
            self.load_thread.quit
        )
        self.load_thread.finished.connect(
            self._cleanup_load_thread
        )

        self.load_thread.start()

    def _show_sources(
        self,
        devices,
        folders: list[Path],
    ) -> None:
        """Display discovered release sources."""

        self.devices = devices
        self.release_folders = folders

        self.release_combo.clear()

        for folder in folders:
            self.release_combo.addItem(
                f"{folder.name}  —  {folder}"
            )

        self.source_status.setText(
            f"{len(devices)} device(s) • {len(folders)} release(s)"
        )

        self.build_plan_button.setEnabled(
            bool(devices and folders)
        )

    def _load_failed(self, message: str) -> None:
        """Display release-source loading failure."""

        self.source_status.setText("Failed")
        self._append_log(
            f"✗ Could not load release sources: {message}"
        )

    def _cleanup_load_thread(self) -> None:
        """Release source-loader references."""

        self.load_worker = None
        self.load_thread = None
        self.refresh_button.setEnabled(True)

    def _browse_release_folder(self) -> None:
        """Choose a release folder outside discovered Downloads folders."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Release Folder",
            str(Path.home() / "Downloads"),
        )

        if not selected:
            return

        folder = Path(selected)

        self.release_folders.append(folder)
        self.release_combo.addItem(
            f"{folder.name}  —  {folder}"
        )
        self.release_combo.setCurrentIndex(
            len(self.release_folders) - 1
        )

        self.build_plan_button.setEnabled(
            bool(self.devices)
        )

    def _source_changed(self) -> None:
        """Invalidate the old release plan."""

        self.plan = None
        self.run_button.setEnabled(False)
        self.plan_table.setRowCount(0)

    def build_plan(self) -> None:
        """Build the release update plan."""

        index = self.release_combo.currentIndex()

        if (
            index < 0
            or index >= len(self.release_folders)
            or not self.devices
        ):
            return

        folder = self.release_folders[index]

        try:
            self.plan = build_release_update_plan(
                folder,
                self.devices,
            )
        except Exception as error:
            self._append_log(
                f"✗ Could not build release plan: {error}"
            )
            return

        self.skip_apks_checkbox.setChecked(False)
        self.skip_jar_checkbox.setChecked(
            not self.plan.upload_jar
        )

        self._append_log("")
        self._append_log(
            f"Selected release folder: {folder}"
        )

        self._render_plan()

    def _render_plan(self) -> None:
        """Render the current APK and JAR plan."""

        if self.plan is None:
            self.plan_table.setRowCount(0)
            self.run_button.setEnabled(False)
            return

        rows = len(self.plan.apk_plan) + 1
        self.plan_table.setRowCount(rows)

        for row, item in enumerate(
            self.plan.apk_plan
        ):
            if item.apk_path is None:
                file_name = "NO MATCHING APK FOUND"
                action = (
                    "SKIP"
                    if self.plan.install_apk
                    else "SKIP"
                )
            else:
                file_name = item.apk_path.name
                action = (
                    "INSTALL"
                    if self.plan.install_apk
                    else "SKIP"
                )

            values = [
                "APK",
                item.device.name,
                file_name,
                action,
            ]

            for column, value in enumerate(values):
                self.plan_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

        jar_row = rows - 1

        if self.plan.jar_file is None:
            jar_name = "JAR NOT FOUND"
            jar_action = "SKIP"
        else:
            jar_name = self.plan.jar_file.name
            jar_action = (
                "UPLOAD"
                if self.plan.upload_jar
                else "SKIP"
            )

        for column, value in enumerate(
            [
                "JAR",
                "Racer Groundlord",
                jar_name,
                jar_action,
            ]
        ):
            self.plan_table.setItem(
                jar_row,
                column,
                QTableWidgetItem(value),
            )

        self.plan_table.resizeColumnsToContents()

        missing_apks = any(
            item.apk_path is None
            for item in self.plan.apk_plan
        )

        actionable = (
            (
                self.plan.install_apk
                and any(
                    item.apk_path is not None
                    for item in self.plan.apk_plan
                )
            )
            or (
                self.plan.upload_jar
                and self.plan.jar_file is not None
            )
        )

        self.run_button.setEnabled(actionable)

        if missing_apks and self.plan.install_apk:
            self._append_log(
                "⚠ One or more connected devices have no matching APK. "
                "They will be skipped unless you choose another APK folder."
            )

        if (
            self.plan.jar_file is None
            and self.plan.upload_jar
        ):
            self._append_log(
                "⚠ Racer Groundlord JAR was not found."
            )

    def _plan_option_changed(self) -> None:
        """Apply skip options to the current plan."""

        if self.plan is None:
            return

        if self.skip_apks_checkbox.isChecked():
            skip_apk_install(self.plan)
        else:
            self.plan.install_apk = True

        if self.skip_jar_checkbox.isChecked():
            skip_jar_upload(self.plan)
        else:
            self.plan.upload_jar = (
                self.plan.jar_file is not None
            )

        self._render_plan()

    def _choose_apk_folder(self) -> None:
        """Replace the APK source folder."""

        if self.plan is None:
            return

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose APK Folder",
            str(Path.home() / "Downloads"),
        )

        if not selected:
            return

        change_apk_folder(
            self.plan,
            Path(selected),
        )
        self.skip_apks_checkbox.setChecked(False)

        self._append_log(
            f"APK source changed to: {selected}"
        )
        self._render_plan()

    def _choose_jar(self) -> None:
        """Replace the selected Groundlord JAR."""

        if self.plan is None:
            return

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
            self._append_log(
                "✗ JAR must be named racer-groundlord.jar"
            )
            return

        change_jar_file(
            self.plan,
            jar_path,
        )
        self.skip_jar_checkbox.setChecked(False)

        self._append_log(
            f"JAR changed to: {jar_path}"
        )
        self._render_plan()

    def run_release(self) -> None:
        """Confirm and execute the final release plan."""

        if self.plan is None:
            return

        confirmation = QMessageBox.question(
            self,
            "Run Full Release Update",
            "Run the APK and JAR actions shown in the release plan?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            self._append_log(
                "Full release update cancelled."
            )
            return

        self.run_button.setEnabled(False)
        self.build_plan_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        total_steps = (
            len(self.plan.apk_plan)
            if self.plan.install_apk
            else 0
        ) + (
            1 if self.plan.upload_jar else 0
        )

        self.progress.setRange(
            0,
            max(total_steps, 1),
        )
        self.progress.setValue(0)

        self.activity_status.setText("Running")
        self._append_log("")
        self._append_log(
            "Starting full release update..."
        )

        self.execution_thread = QThread()
        self.execution_worker = ReleaseExecutionWorker(
            self.plan
        )
        self.execution_worker.moveToThread(
            self.execution_thread
        )

        self.execution_thread.started.connect(
            self.execution_worker.run
        )
        self.execution_worker.status.connect(
            self._append_log
        )
        self.execution_worker.progress.connect(
            self._update_progress
        )
        self.execution_worker.finished.connect(
            self._show_results
        )
        self.execution_worker.failed.connect(
            self._execution_failed
        )
        self.execution_worker.finished.connect(
            self.execution_thread.quit
        )
        self.execution_worker.failed.connect(
            self.execution_thread.quit
        )
        self.execution_thread.finished.connect(
            self._cleanup_execution_thread
        )

        self.execution_thread.start()

    def _update_progress(
        self,
        completed: int,
        total: int,
    ) -> None:
        """Update release execution progress."""

        self.progress.setRange(
            0,
            max(total, 1),
        )
        self.progress.setValue(completed)

    def _show_results(
        self,
        apk_results: list[InstallationResult],
        jar_result: bool | None,
        jar_blocked: bool,
    ) -> None:
        """Display full release update results."""

        if self.plan is None:
            return

        self._append_log("")
        self._append_log("Full Release Update Results")

        results_by_serial = {
            result.device.serial: result
            for result in apk_results
        }

        for item in self.plan.apk_plan:
            if not self.plan.install_apk:
                result_text = "SKIPPED"
            elif item.apk_path is None:
                result_text = (
                    "SKIPPED - No matching APK"
                )
            else:
                result = results_by_serial.get(
                    item.device.serial
                )

                if result is None:
                    result_text = "NOT RUN"
                elif result.status == "success":
                    result_text = "SUCCESS"
                elif result.status == "skipped":
                    result_text = "SKIPPED"
                else:
                    result_text = (
                        f"FAILED - {result.message}"
                        if result.message
                        else "FAILED"
                    )

            self._append_log(
                f"APK | {item.device.name} | {result_text}"
            )

        if jar_blocked:
            jar_text = (
                "NOT RUN - APK installation failed"
            )
        elif not self.plan.upload_jar:
            jar_text = "SKIPPED"
        elif jar_result is True:
            jar_text = "SUCCESS"
        elif jar_result is False:
            jar_text = "FAILED"
        else:
            jar_text = "NOT RUN"

        self._append_log(
            f"JAR | Racer Groundlord | {jar_text}"
        )
        self._append_log("")
        self._append_log(
            "Full release update finished."
        )

        failed = any(
            result.status == "failed"
            for result in apk_results
        ) or jar_result is False

        self.activity_status.setText(
            "Completed with errors"
            if failed
            else "✓ Completed"
        )

    def _execution_failed(self, message: str) -> None:
        """Display unexpected release execution failure."""

        self._append_log(
            f"✗ Full release update failed: {message}"
        )
        self.activity_status.setText("Failed")

    def _cleanup_execution_thread(self) -> None:
        """Release execution worker references."""

        self.execution_worker = None
        self.execution_thread = None
        self.refresh_button.setEnabled(True)
        self.build_plan_button.setEnabled(
            bool(self.devices and self.release_folders)
        )
        self.run_button.setEnabled(
            self.plan is not None
        )

    def _append_log(self, message: str) -> None:
        """Append one deployment activity message."""

        self.log.appendPlainText(message)
