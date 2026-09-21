"""PySide6 Folders Reset page."""

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from racer_team_toolkit.adb.functions import get_connected_android_devices
from racer_team_toolkit.config import VIDEO_REMOTE_PATH, AndroidDevice
from racer_team_toolkit.quick_reset.functions import (
    build_reset_plan_counts,
    reset_remote_folder,
)


class ResetScanWorker(QObject):
    """Count files for a proposed reset plan."""

    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        devices: list[AndroidDevice],
        reset_plan: dict[str, set[str]],
    ) -> None:
        super().__init__()
        self.devices = devices
        self.reset_plan = reset_plan

    def run(self) -> None:
        """Count files in selected remote folders."""

        try:
            self.status.emit("Checking selected folders...")
            counts = build_reset_plan_counts(
                self.devices,
                self.reset_plan,
            )
            self.finished.emit(counts)

        except Exception as error:
            self.failed.emit(str(error))


class ResetApplyWorker(QObject):
    """Delete selected remote folder contents."""

    status = Signal(str)
    progress = Signal(int, int)
    finished = Signal(bool)
    failed = Signal(str)

    def __init__(
        self,
        devices: list[AndroidDevice],
        reset_plan: dict[str, set[str]],
    ) -> None:
        super().__init__()
        self.devices = devices
        self.reset_plan = reset_plan

    def run(self) -> None:
        """Apply the reset plan."""

        steps: list[tuple[AndroidDevice, str, str]] = []

        for device in self.devices:
            folders = self.reset_plan.get(
                device.serial,
                set(),
            )

            if "reff" in folders:
                steps.append(
                    (
                        device,
                        "REFF",
                        device.remote_log_path,
                    )
                )

            if "videos" in folders:
                steps.append(
                    (
                        device,
                        "Screen Videos",
                        VIDEO_REMOTE_PATH,
                    )
                )

        all_successful = True
        total = len(steps)

        try:
            for index, (
                device,
                label,
                remote_path,
            ) in enumerate(steps, start=1):
                self.status.emit(
                    f"Resetting {label} on {device.name}..."
                )

                success = reset_remote_folder(
                    device,
                    remote_path,
                )

                if success:
                    self.status.emit(
                        f"✓ {device.name}: {label} folder reset"
                    )
                else:
                    all_successful = False
                    self.status.emit(
                        f"✗ {device.name}: failed to reset {label}"
                    )

                self.progress.emit(
                    index,
                    total,
                )

            self.finished.emit(all_successful)

        except Exception as error:
            self.failed.emit(str(error))


class FoldersResetPage(QWidget):
    """Desktop interface for Quick Reset and Custom Reset."""

    def __init__(self) -> None:
        super().__init__()

        self.devices: list[AndroidDevice] = []
        self.device_rows: dict[
            str,
            tuple[QCheckBox, QCheckBox, QCheckBox],
        ] = {}
        self.reset_plan: dict[str, set[str]] = {}
        self.counts: dict[str, dict[str, int]] = {}

        self.scan_thread: QThread | None = None
        self.scan_worker: ResetScanWorker | None = None
        self.apply_thread: QThread | None = None
        self.apply_worker: ResetApplyWorker | None = None

        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        """Build the reset page."""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(16)

        title = QLabel("Folders Reset")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Clear REFF and Screen Videos folders on connected Android devices."
        )
        subtitle.setObjectName("pageSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(16)

        devices_card = QFrame()
        devices_card.setObjectName("workflowCard")
        devices_layout = QVBoxLayout(devices_card)
        devices_layout.setContentsMargins(22, 20, 22, 20)
        devices_layout.setSpacing(12)

        header = QHBoxLayout()

        devices_title = QLabel("Devices & Folders")
        devices_title.setObjectName("sectionTitle")

        self.device_status = QLabel("Checking...")
        self.device_status.setObjectName("statusPill")

        header.addWidget(devices_title)
        header.addStretch()
        header.addWidget(self.device_status)

        column_header = QHBoxLayout()

        device_column = QLabel("Device")
        device_column.setObjectName("mutedText")

        reff_column = QLabel("REFF")
        reff_column.setObjectName("mutedText")

        videos_column = QLabel("Videos")
        videos_column.setObjectName("mutedText")

        column_header.addWidget(device_column, stretch=1)
        column_header.addWidget(reff_column)
        column_header.addSpacing(20)
        column_header.addWidget(videos_column)

        self.device_list_layout = QVBoxLayout()
        self.device_list_layout.setSpacing(8)

        quick_button = QPushButton(
            "Quick Reset: Select Everything"
        )
        quick_button.setObjectName("secondaryButton")
        quick_button.clicked.connect(
            self._select_everything
        )

        self.refresh_button = QPushButton(
            "Refresh Devices"
        )
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(
            self.refresh_devices
        )

        device_buttons = QHBoxLayout()
        device_buttons.addWidget(quick_button)
        device_buttons.addWidget(self.refresh_button)
        device_buttons.addStretch()

        devices_layout.addLayout(header)
        devices_layout.addLayout(column_header)
        devices_layout.addLayout(self.device_list_layout)
        devices_layout.addStretch()
        devices_layout.addLayout(device_buttons)

        review_card = QFrame()
        review_card.setObjectName("workflowCard")
        review_layout = QVBoxLayout(review_card)
        review_layout.setContentsMargins(22, 20, 22, 20)
        review_layout.setSpacing(12)

        review_title = QLabel("Reset Plan")
        review_title.setObjectName("sectionTitle")

        self.plan_summary = QLabel(
            "Select folders, then review the reset plan."
        )
        self.plan_summary.setObjectName("mutedText")
        self.plan_summary.setWordWrap(True)

        self.log = QPlainTextEdit()
        self.log.setObjectName("installLog")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText(
            "Reset plan and activity will appear here..."
        )

        self.progress = QProgressBar()
        self.progress.setObjectName("operationProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Step %v of %m")

        self.review_button = QPushButton(
            "Review Reset Plan"
        )
        self.review_button.setObjectName("secondaryButton")
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(
            self.review_plan
        )

        self.reset_button = QPushButton(
            "Reset Selected Folders"
        )
        self.reset_button.setObjectName("dangerButton")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(
            self.apply_reset
        )

        review_layout.addWidget(review_title)
        review_layout.addWidget(self.plan_summary)
        review_layout.addWidget(self.log, stretch=1)
        review_layout.addWidget(self.progress)
        review_layout.addWidget(self.review_button)
        review_layout.addWidget(self.reset_button)

        controls.addWidget(devices_card, stretch=1)
        controls.addWidget(review_card, stretch=1)

        root.addLayout(controls, stretch=1)

    def refresh_devices(self) -> None:
        """Detect connected devices."""

        self.refresh_button.setEnabled(False)
        self.device_status.setText("Checking")

        try:
            devices = get_connected_android_devices()
        except Exception as error:
            self.device_status.setText("Failed")
            self._append_log(
                f"✗ Device detection failed: {error}"
            )
            self.refresh_button.setEnabled(True)
            return

        self.devices = devices
        self.device_rows.clear()
        self._clear_device_rows()

        for device in devices:
            row = QFrame()
            row.setObjectName("selectionRow")

            layout = QHBoxLayout(row)
            layout.setContentsMargins(14, 11, 14, 11)

            selected = QCheckBox()
            selected.setChecked(True)

            details = QVBoxLayout()

            name = QLabel(device.name)
            name.setObjectName("deviceName")

            serial = QLabel(device.serial)
            serial.setObjectName("deviceSerial")

            details.addWidget(name)
            details.addWidget(serial)

            reff = QCheckBox("REFF")
            reff.setChecked(True)

            videos = QCheckBox("Videos")
            videos.setChecked(True)

            for checkbox in (
                selected,
                reff,
                videos,
            ):
                checkbox.stateChanged.connect(
                    self._selection_changed
                )

            layout.addWidget(selected)
            layout.addLayout(details, stretch=1)
            layout.addWidget(reff)
            layout.addWidget(videos)

            self.device_list_layout.addWidget(row)

            self.device_rows[device.serial] = (
                selected,
                reff,
                videos,
            )

        count = len(devices)
        self.device_status.setText(
            f"{count} device" if count == 1 else f"{count} devices"
        )

        if not devices:
            empty = QLabel(
                "No supported Android devices connected."
            )
            empty.setObjectName("emptyState")
            self.device_list_layout.addWidget(empty)

        self.refresh_button.setEnabled(True)
        self._selection_changed()

    def _select_everything(self) -> None:
        """Select every connected device and folder."""

        for selected, reff, videos in self.device_rows.values():
            selected.setChecked(True)
            reff.setChecked(True)
            videos.setChecked(True)

        self._selection_changed()

    def _selection_changed(self) -> None:
        """Invalidate an old plan when selection changes."""

        self.reset_button.setEnabled(False)
        self.counts = {}
        self.reset_plan = {}

        has_selection = any(
            selected.isChecked()
            and (
                reff.isChecked()
                or videos.isChecked()
            )
            for selected, reff, videos in self.device_rows.values()
        )

        self.review_button.setEnabled(has_selection)

    def _build_plan(self) -> tuple[
        list[AndroidDevice],
        dict[str, set[str]],
    ]:
        """Build a reset plan from GUI selections."""

        selected_devices: list[AndroidDevice] = []
        reset_plan: dict[str, set[str]] = {}

        for device in self.devices:
            row = self.device_rows.get(
                device.serial
            )

            if row is None:
                continue

            selected, reff, videos = row

            if not selected.isChecked():
                continue

            folders: set[str] = set()

            if reff.isChecked():
                folders.add("reff")

            if videos.isChecked():
                folders.add("videos")

            if folders:
                selected_devices.append(device)
                reset_plan[device.serial] = folders

        return selected_devices, reset_plan

    def review_plan(self) -> None:
        """Count files for the selected reset plan."""

        if self.scan_thread is not None and self.scan_thread.isRunning():
            return

        selected_devices, reset_plan = self._build_plan()

        if not selected_devices:
            return

        self.reset_plan = reset_plan
        self.log.clear()
        self._append_log("Checking selected folders...")

        self.review_button.setEnabled(False)
        self.reset_button.setEnabled(False)

        self.scan_thread = QThread()
        self.scan_worker = ResetScanWorker(
            selected_devices,
            reset_plan,
        )
        self.scan_worker.moveToThread(
            self.scan_thread
        )

        self.scan_thread.started.connect(
            self.scan_worker.run
        )
        self.scan_worker.status.connect(
            self._append_log
        )
        self.scan_worker.finished.connect(
            lambda counts: self._show_plan(
                selected_devices,
                counts,
            )
        )
        self.scan_worker.failed.connect(
            self._scan_failed
        )
        self.scan_worker.finished.connect(
            self.scan_thread.quit
        )
        self.scan_worker.failed.connect(
            self.scan_thread.quit
        )
        self.scan_thread.finished.connect(
            self._cleanup_scan_thread
        )

        self.scan_thread.start()

    def _show_plan(
        self,
        devices: list[AndroidDevice],
        counts: dict[str, dict[str, int]],
    ) -> None:
        """Render reset counts."""

        self.counts = counts
        self.log.clear()

        total_files = 0

        self._append_log("Reset Plan")
        self._append_log("")

        for device in devices:
            folders = self.reset_plan.get(
                device.serial,
                set(),
            )
            device_counts = counts.get(
                device.serial,
                {"reff": 0, "videos": 0},
            )

            self._append_log(device.name)

            if "reff" in folders:
                reff_count = device_counts["reff"]
                total_files += reff_count
                self._append_log(
                    f"  REFF: {reff_count} file(s)"
                )

            if "videos" in folders:
                video_count = device_counts["videos"]
                total_files += video_count
                self._append_log(
                    f"  Screen Videos: {video_count} file(s)"
                )

        self._append_log("")
        self._append_log(
            f"Total files to delete: {total_files}"
        )

        if total_files == 0:
            self.plan_summary.setText(
                "Selected folders are already empty."
            )
            self.reset_button.setEnabled(False)
        else:
            self.plan_summary.setText(
                f"{total_files} file(s) will be permanently deleted."
            )
            self.reset_button.setEnabled(True)

    def _scan_failed(self, message: str) -> None:
        """Display scan failure."""

        self._append_log(
            f"✗ Could not build reset plan: {message}"
        )

    def _cleanup_scan_thread(self) -> None:
        """Release scan worker references."""

        self.scan_worker = None
        self.scan_thread = None
        self.review_button.setEnabled(True)

    def apply_reset(self) -> None:
        """Confirm and apply the reviewed plan."""

        selected_devices, reset_plan = self._build_plan()

        if (
            not selected_devices
            or reset_plan != self.reset_plan
        ):
            self._append_log(
                "Selection changed. Review the reset plan again."
            )
            self.reset_button.setEnabled(False)
            return

        confirmation = QMessageBox.warning(
            self,
            "Confirm Folder Reset",
            "This permanently deletes the selected files from "
            "the connected devices.\n\nContinue with reset?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            self._append_log("Reset cancelled.")
            return

        self.reset_button.setEnabled(False)
        self.review_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        steps = sum(
            len(folders)
            for folders in reset_plan.values()
        )

        self.progress.setRange(
            0,
            max(steps, 1),
        )
        self.progress.setValue(0)

        self._append_log("")
        self._append_log("Starting reset...")

        self.apply_thread = QThread()
        self.apply_worker = ResetApplyWorker(
            selected_devices,
            reset_plan,
        )
        self.apply_worker.moveToThread(
            self.apply_thread
        )

        self.apply_thread.started.connect(
            self.apply_worker.run
        )
        self.apply_worker.status.connect(
            self._append_log
        )
        self.apply_worker.progress.connect(
            self._update_progress
        )
        self.apply_worker.finished.connect(
            self._reset_finished
        )
        self.apply_worker.failed.connect(
            self._reset_failed
        )
        self.apply_worker.finished.connect(
            self.apply_thread.quit
        )
        self.apply_worker.failed.connect(
            self.apply_thread.quit
        )
        self.apply_thread.finished.connect(
            self._cleanup_apply_thread
        )

        self.apply_thread.start()

    def _update_progress(
        self,
        completed: int,
        total: int,
    ) -> None:
        """Update reset operation progress."""

        self.progress.setRange(
            0,
            max(total, 1),
        )
        self.progress.setValue(completed)

    def _reset_finished(self, success: bool) -> None:
        """Display final reset result."""

        self._append_log("")

        if success:
            self._append_log(
                "✓ Reset completed successfully."
            )
            self.plan_summary.setText(
                "Reset completed successfully."
            )
        else:
            self._append_log(
                "✗ Reset completed with errors."
            )
            self.plan_summary.setText(
                "Reset completed with errors."
            )

        self.reset_plan = {}
        self.counts = {}

    def _reset_failed(self, message: str) -> None:
        """Display an unexpected reset failure."""

        self._append_log(
            f"✗ Reset failed: {message}"
        )
        self.plan_summary.setText(
            "Reset failed."
        )

    def _cleanup_apply_thread(self) -> None:
        """Release reset worker references."""

        self.apply_worker = None
        self.apply_thread = None
        self.review_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.refresh_devices()

    def _append_log(self, message: str) -> None:
        """Append text to the reset activity log."""

        self.log.appendPlainText(message)

    def _clear_device_rows(self) -> None:
        """Remove old device rows."""

        while self.device_list_layout.count():
            item = self.device_list_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
