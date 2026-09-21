"""PySide6 APK Installer workflow."""

from __future__ import annotations

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
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from rich.console import Console

from racer_team_toolkit.adb.functions import get_connected_android_devices
from racer_team_toolkit.apk_installer.functions import (
    InstallationPlan,
    InstallationResult,
    build_installation_plan,
    get_folders_in_downloads,
    run_installation,
)
from racer_team_toolkit.config import AndroidDevice


class DeviceLoader(QObject):
    """Detect connected Android devices without blocking the GUI."""

    finished = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Detect supported Android devices."""

        try:
            self.finished.emit(get_connected_android_devices())
        except Exception as error:
            self.failed.emit(str(error))


class InstallationWorker(QObject):
    """Install APKs in a worker thread."""

    progress = Signal(int, int, str)
    log = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, plan: list[InstallationPlan]) -> None:
        super().__init__()
        self.plan = plan

    def run(self) -> None:
        """Install each planned APK sequentially."""

        results: list[InstallationResult] = []
        quiet_console = Console(file=io.StringIO(), force_terminal=False)
        total = len(self.plan)

        try:
            for index, item in enumerate(self.plan, start=1):
                self.progress.emit(
                    index - 1,
                    total,
                    f"Installing on {item.device.name}...",
                )
                results.append(
                    run_installation(
                        item,
                        quiet_console,
                        status_callback=self.log.emit,
                    )
                )
                self.progress.emit(
                    index,
                    total,
                    f"Finished {item.device.name}",
                )

        except Exception as error:
            self.failed.emit(str(error))
            return

        self.finished.emit(results)


class ApkInstallerPage(QWidget):
    """Desktop workflow for installing APKs on connected devices."""

    def __init__(self) -> None:
        super().__init__()

        self.devices: list[AndroidDevice] = []
        self.device_checkboxes: list[tuple[AndroidDevice, QCheckBox]] = []
        self.selected_devices: list[AndroidDevice] = []
        self.source_folders: list[Path] = []
        self.plan: list[InstallationPlan] = []
        self.results: list[InstallationResult] = []

        self.device_thread: QThread | None = None
        self.device_worker: DeviceLoader | None = None
        self.install_thread: QThread | None = None
        self.install_worker: InstallationWorker | None = None

        self.steps = QStackedWidget()
        self._initial_load_done = False

        self._build_ui()

    def on_activated(self) -> None:
        """Load devices the first time this page is opened."""

        if self._initial_load_done:
            return

        self._initial_load_done = True
        self.refresh_devices()

    def _build_ui(self) -> None:
        """Build the APK Installer workflow."""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(14)

        title = QLabel("APK Installer")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Select connected devices, choose an APK source, review the plan, and install."
        )
        subtitle.setObjectName("pageSubtitle")

        self.step_label = QLabel()
        self.step_label.setObjectName("workflowSteps")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(8)
        root.addWidget(self.step_label)
        root.addSpacing(8)
        root.addWidget(self.steps, stretch=1)

        self.steps.addWidget(self._build_devices_step())
        self.steps.addWidget(self._build_source_step())
        self.steps.addWidget(self._build_review_step())
        self.steps.addWidget(self._build_install_step())
        self.steps.addWidget(self._build_results_step())

        self._show_step(0)

    def _build_devices_step(self) -> QWidget:
        """Build target-device selection."""

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("workflowCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        header = QHBoxLayout()

        heading = QLabel("1. Choose Target Devices")
        heading.setObjectName("sectionTitle")

        self.device_status = QLabel("Checking...")
        self.device_status.setObjectName("mutedText")

        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self.device_status)

        self.device_list_layout = QVBoxLayout()
        self.device_list_layout.setSpacing(8)

        card_layout.addLayout(header)
        card_layout.addLayout(self.device_list_layout)

        buttons = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh Devices")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self.refresh_devices)

        self.devices_continue_button = QPushButton("Continue")
        self.devices_continue_button.setObjectName("primaryButton")
        self.devices_continue_button.setEnabled(False)
        self.devices_continue_button.clicked.connect(self._continue_from_devices)

        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        buttons.addWidget(self.devices_continue_button)

        layout.addWidget(card)
        layout.addStretch()
        layout.addLayout(buttons)

        return page

    def _build_source_step(self) -> QWidget:
        """Build APK source selection."""

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("workflowCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        heading = QLabel("2. Choose APK Source")
        heading.setObjectName("sectionTitle")

        description = QLabel("Choose Downloads or a folder that directly contains the APK files.")
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        self.folder_combo = QComboBox()
        self.folder_combo.setObjectName("folderCombo")

        browse_button = QPushButton("Browse for Folder...")
        browse_button.setObjectName("secondaryButton")
        browse_button.clicked.connect(self._browse_folder)

        self.source_error = QLabel()
        self.source_error.setObjectName("errorText")
        self.source_error.setWordWrap(True)
        self.source_error.hide()

        card_layout.addWidget(heading)
        card_layout.addWidget(description)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.folder_combo)
        card_layout.addWidget(browse_button)
        card_layout.addWidget(self.source_error)

        buttons = QHBoxLayout()

        back_button = QPushButton("Back")
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(lambda: self._show_step(0))

        review_button = QPushButton("Review Plan")
        review_button.setObjectName("primaryButton")
        review_button.clicked.connect(self._review_plan)

        buttons.addWidget(back_button)
        buttons.addStretch()
        buttons.addWidget(review_button)

        layout.addWidget(card)
        layout.addStretch()
        layout.addLayout(buttons)

        return page

    def _build_review_step(self) -> QWidget:
        """Build installation-plan review."""

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("workflowCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        heading = QLabel("3. Review Installation Plan")
        heading.setObjectName("sectionTitle")

        self.review_source = QLabel()
        self.review_source.setObjectName("mutedText")
        self.review_source.setWordWrap(True)

        self.review_list_layout = QVBoxLayout()
        self.review_list_layout.setSpacing(8)

        card_layout.addWidget(heading)
        card_layout.addWidget(self.review_source)
        card_layout.addLayout(self.review_list_layout)

        buttons = QHBoxLayout()

        back_button = QPushButton("Back")
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(lambda: self._show_step(1))

        self.install_button = QPushButton("Install APKs")
        self.install_button.setObjectName("primaryButton")
        self.install_button.clicked.connect(self._start_installation)

        buttons.addWidget(back_button)
        buttons.addStretch()
        buttons.addWidget(self.install_button)

        layout.addWidget(card)
        layout.addStretch()
        layout.addLayout(buttons)

        return page

    def _build_install_step(self) -> QWidget:
        """Build installation-progress screen."""

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("workflowCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(16)

        heading = QLabel("4. Installing APKs")
        heading.setObjectName("sectionTitle")

        self.install_status = QLabel("Preparing installation...")
        self.install_status.setObjectName("mutedText")

        self.install_progress = QProgressBar()
        self.install_progress.setObjectName("installProgress")
        self.install_progress.setTextVisible(True)
        self.install_progress.setFormat("Device %v of %m")

        self.install_log = QPlainTextEdit()
        self.install_log.setObjectName("installLog")
        self.install_log.setReadOnly(True)
        self.install_log.setPlaceholderText("Installation activity will appear here...")

        card_layout.addWidget(heading)
        card_layout.addWidget(self.install_status)
        card_layout.addWidget(self.install_progress)
        card_layout.addWidget(self.install_log)

        layout.addWidget(card)
        layout.addStretch()

        return page

    def _build_results_step(self) -> QWidget:
        """Build installation-results screen."""

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("workflowCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        heading = QLabel("5. Installation Results")
        heading.setObjectName("sectionTitle")

        self.results_summary = QLabel()
        self.results_summary.setObjectName("mutedText")

        self.results_list_layout = QVBoxLayout()
        self.results_list_layout.setSpacing(8)

        card_layout.addWidget(heading)
        card_layout.addWidget(self.results_summary)
        card_layout.addLayout(self.results_list_layout)

        buttons = QHBoxLayout()

        start_over_button = QPushButton("Install More APKs")
        start_over_button.setObjectName("secondaryButton")
        start_over_button.clicked.connect(self._start_over)

        buttons.addStretch()
        buttons.addWidget(start_over_button)

        layout.addWidget(card)
        layout.addStretch()
        layout.addLayout(buttons)

        return page

    def _show_step(self, index: int) -> None:
        """Show a workflow step and update the step indicator."""

        labels = [
            "Devices",
            "APK Source",
            "Review",
            "Install",
            "Results",
        ]

        parts = []

        for step_index, label in enumerate(labels):
            if step_index == index:
                parts.append(f"<b>{step_index + 1} {label}</b>")
            else:
                parts.append(f"{step_index + 1} {label}")

        self.step_label.setText("  ›  ".join(parts))
        self.steps.setCurrentIndex(index)

    def refresh_devices(self) -> None:
        """Detect supported Android devices in a worker thread."""

        if self.device_thread is not None and self.device_thread.isRunning():
            return

        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Checking...")
        self.devices_continue_button.setEnabled(False)
        self.device_status.setText("Detecting devices...")

        self.device_thread = QThread()
        self.device_worker = DeviceLoader()
        self.device_worker.moveToThread(self.device_thread)

        self.device_thread.started.connect(self.device_worker.run)
        self.device_worker.finished.connect(self._show_devices)
        self.device_worker.failed.connect(self._show_device_error)
        self.device_worker.finished.connect(self.device_thread.quit)
        self.device_worker.failed.connect(self.device_thread.quit)
        self.device_thread.finished.connect(self._cleanup_device_thread)

        self.device_thread.start()

    def _show_devices(self, devices: list[AndroidDevice]) -> None:
        """Render connected devices as checked targets."""

        self.devices = devices
        self.device_checkboxes.clear()
        self._clear_layout(self.device_list_layout)

        if not devices:
            label = QLabel("No supported Android devices are connected.")
            label.setObjectName("emptyState")
            self.device_list_layout.addWidget(label)
            self.device_status.setText("0 devices")
            return

        for device in devices:
            row = QFrame()
            row.setObjectName("selectionRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)

            checkbox = QCheckBox()
            checkbox.setChecked(True)

            info = QVBoxLayout()

            name = QLabel(device.name)
            name.setObjectName("deviceName")

            serial = QLabel(f"Serial: {device.serial}")
            serial.setObjectName("deviceSerial")

            info.addWidget(name)
            info.addWidget(serial)

            status = QLabel("● Connected")
            status.setObjectName("deviceConnected")

            row_layout.addWidget(checkbox)
            row_layout.addLayout(info)
            row_layout.addStretch()
            row_layout.addWidget(status)

            self.device_list_layout.addWidget(row)
            self.device_checkboxes.append((device, checkbox))

        count = len(devices)
        self.device_status.setText(f"{count} device" if count == 1 else f"{count} devices")
        self.devices_continue_button.setEnabled(True)

    def _show_device_error(self, message: str) -> None:
        """Display an ADB detection error."""

        self._clear_layout(self.device_list_layout)

        label = QLabel(f"Device detection failed: {message}")
        label.setObjectName("errorText")
        label.setWordWrap(True)

        self.device_list_layout.addWidget(label)
        self.device_status.setText("Detection failed")

    def _cleanup_device_thread(self) -> None:
        """Release device-detection thread references."""

        self.device_worker = None
        self.device_thread = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh Devices")

    def _continue_from_devices(self) -> None:
        """Store selected targets and continue to APK source selection."""

        self.selected_devices = [
            device for device, checkbox in self.device_checkboxes if checkbox.isChecked()
        ]

        if not self.selected_devices:
            self.device_status.setText("Select at least one device")
            return

        self._load_source_folders()
        self._show_step(1)

    def _load_source_folders(self) -> None:
        """Load APK-containing folders from Downloads."""

        self.folder_combo.clear()
        self.source_folders = []
        self.source_error.hide()

        try:
            self.source_folders = get_folders_in_downloads()
        except Exception as error:
            self.source_error.setText(f"Could not scan Downloads: {error}")
            self.source_error.show()
            return

        for folder in self.source_folders:
            self.folder_combo.addItem(
                f"{folder.name}  —  {folder}",
            )

        if not self.source_folders:
            self.source_error.setText(
                "No APK folders were found in Downloads. Use Browse for Folder."
            )
            self.source_error.show()

    def _browse_folder(self) -> None:
        """Let the user choose an APK folder outside the discovered list."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose APK Folder",
            str(Path.home() / "Downloads"),
        )

        if not selected:
            return

        folder = Path(selected)

        self.source_folders.append(folder)
        self.folder_combo.addItem(f"{folder.name}  —  {folder}")
        self.folder_combo.setCurrentIndex(len(self.source_folders) - 1)
        self.source_error.hide()

    def _review_plan(self) -> None:
        """Build and display the installation plan."""

        index = self.folder_combo.currentIndex()

        if index < 0 or index >= len(self.source_folders):
            self.source_error.setText("Choose an APK folder first.")
            self.source_error.show()
            return

        folder = self.source_folders[index]

        try:
            self.plan = build_installation_plan(
                folder,
                self.selected_devices,
            )
        except Exception as error:
            self.source_error.setText(f"Could not build installation plan: {error}")
            self.source_error.show()
            return

        self.review_source.setText(f"Source folder: {folder}")
        self._clear_layout(self.review_list_layout)

        matching_count = 0

        for item in self.plan:
            row = QFrame()
            row.setObjectName("selectionRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)

            device_label = QLabel(item.device.name)
            device_label.setObjectName("deviceName")

            if item.apk_path is None:
                apk_label = QLabel("NO MATCHING APK FOUND")
                apk_label.setObjectName("missingText")
            else:
                matching_count += 1
                apk_label = QLabel(item.apk_path.name)
                apk_label.setObjectName("successText")

            apk_label.setWordWrap(True)

            row_layout.addWidget(device_label)
            row_layout.addStretch()
            row_layout.addWidget(apk_label, stretch=1)

            self.review_list_layout.addWidget(row)

        self.install_button.setEnabled(matching_count > 0)
        self._show_step(2)

    def _start_installation(self) -> None:
        """Run the selected APK installations in a worker thread."""

        if self.install_thread is not None and self.install_thread.isRunning():
            return

        self._show_step(3)

        total = len(self.plan)
        self.install_progress.setRange(0, total)
        self.install_progress.setValue(0)
        self.install_status.setText("Starting installation...")
        self.install_log.clear()
        self.install_log.appendPlainText("Starting APK installation...")

        self.install_thread = QThread()
        self.install_worker = InstallationWorker(self.plan)
        self.install_worker.moveToThread(self.install_thread)

        self.install_thread.started.connect(self.install_worker.run)
        self.install_worker.progress.connect(self._update_install_progress)
        self.install_worker.log.connect(self._append_install_log)
        self.install_worker.finished.connect(self._show_results)
        self.install_worker.failed.connect(self._show_install_error)
        self.install_worker.finished.connect(self.install_thread.quit)
        self.install_worker.failed.connect(self.install_thread.quit)
        self.install_thread.finished.connect(self._cleanup_install_thread)

        self.install_thread.start()

    def _update_install_progress(
        self,
        completed: int,
        total: int,
        message: str,
    ) -> None:
        """Update installation progress."""

        self.install_progress.setRange(0, total)
        self.install_progress.setValue(completed)
        self.install_status.setText(message)

    def _append_install_log(
        self,
        message: str,
    ) -> None:
        """Append one live installation event to the activity log."""

        self.install_log.appendPlainText(message)
        self.install_status.setText(message)

    def _show_results(self, results: list[InstallationResult]) -> None:
        """Render final per-device installation results."""

        self.results = results
        self._clear_layout(self.results_list_layout)

        successful = sum(result.status == "success" for result in results)
        failed = sum(result.status == "failed" for result in results)
        skipped = sum(result.status == "skipped" for result in results)

        self.results_summary.setText(
            f"Successful: {successful}    Failed: {failed}    Skipped: {skipped}"
        )

        for result in results:
            row = QFrame()
            row.setObjectName("selectionRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)

            device_label = QLabel(result.device.name)
            device_label.setObjectName("deviceName")

            if result.status == "success":
                result_label = QLabel("✓ Success")
                result_label.setObjectName("successText")
            elif result.status == "skipped":
                result_label = QLabel(
                    f"⚠ Skipped{f' — {result.message}' if result.message else ''}"
                )
                result_label.setObjectName("warningText")
            else:
                result_label = QLabel(f"✗ Failed{f' — {result.message}' if result.message else ''}")
                result_label.setObjectName("errorText")

            result_label.setWordWrap(True)

            row_layout.addWidget(device_label)
            row_layout.addStretch()
            row_layout.addWidget(result_label, stretch=1)

            self.results_list_layout.addWidget(row)

        self._show_step(4)

    def _show_install_error(self, message: str) -> None:
        """Show an unexpected installer error as a result."""

        self._clear_layout(self.results_list_layout)
        self.results_summary.setText("Installation stopped unexpectedly.")

        label = QLabel(message)
        label.setObjectName("errorText")
        label.setWordWrap(True)
        self.results_list_layout.addWidget(label)

        self._show_step(4)

    def _cleanup_install_thread(self) -> None:
        """Release installation worker references."""

        self.install_worker = None
        self.install_thread = None

    def _start_over(self) -> None:
        """Reset the workflow for another installation."""

        self.plan = []
        self.results = []
        self.selected_devices = []
        self.refresh_devices()
        self._show_step(0)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        """Delete all widgets from a vertical layout."""

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
