"""PySide6 REFF and video extraction page."""

from datetime import datetime
from pathlib import PurePosixPath

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from racer_team_toolkit.adb.functions import get_connected_android_devices
from racer_team_toolkit.config import LOCAL_DUMP_DIR, AndroidDevice
from racer_team_toolkit.reff_extractor.extraction import create_output_directory
from racer_team_toolkit.reff_extractor.grouping import (
    get_next_flight_number,
    group_files_into_flights,
    group_videos_into_flights,
)
from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
    GroupingWarning,
)
from racer_team_toolkit.reff_extractor.time_adjustment_dataclasses import (
    DeviceTimeInfo,
)
from racer_team_toolkit.reff_extractor.time_adjustment_functions import (
    apply_file_time_corrections,
    build_device_file_corrections,
    format_time_difference,
    get_connected_device_time_info,
    get_devices_needing_time_fix,
    get_devices_with_correct_time,
    get_pc_datetime,
)
from racer_team_toolkit.reff_extractor.transfer import (
    get_transfer_verb,
    process_device,
)


class DeviceTimeWorker(QObject):
    """Detect devices and compare their clocks with the computer."""

    status = Signal(str)
    finished = Signal(object, object, object)
    failed = Signal(str)

    def run(self) -> None:
        """Load connected devices and time information."""

        try:
            self.status.emit("Checking connected Android devices...")
            devices = get_connected_android_devices()

            if not devices:
                self.finished.emit([], [], [])
                return

            self.status.emit(
                f"✓ Connected devices: {len(devices)}"
            )

            for device in devices:
                self.status.emit(
                    f"  {device.name} (Serial: {device.serial})"
                )

            pc_datetime = get_pc_datetime()

            self.status.emit("Checking device clocks...")
            time_info = get_connected_device_time_info(
                devices,
                pc_datetime,
            )
            incorrect = get_devices_needing_time_fix(
                time_info,
            )

            self.status.emit(
                f"PC Time: {pc_datetime:%d-%m-%Y %H:%M:%S}"
            )

            self.finished.emit(
                devices,
                time_info,
                incorrect,
            )

        except Exception as error:
            self.failed.emit(str(error))


class TimeCorrectionWorker(QObject):
    """Correct files belonging to devices with incorrect clocks."""

    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        incorrect_devices: list[DeviceTimeInfo],
    ) -> None:
        super().__init__()
        self.incorrect_devices = incorrect_devices

    def run(self) -> None:
        """Apply file timestamp and filename corrections."""

        corrected_devices: list[AndroidDevice] = []

        try:
            for device_info in self.incorrect_devices:
                device = device_info.device

                self.status.emit("")
                self.status.emit(f"▶ {device.name}")
                self.status.emit(
                    "Wrong device date: "
                    f"{device_info.device_datetime:%d-%m-%Y}"
                )
                self.status.emit(
                    "Time correction: "
                    f"{format_time_difference(device_info.difference_seconds)}"
                )
                self.status.emit(
                    "Scanning affected REFF and screen video files..."
                )

                corrections, reff_count, video_count = (
                    build_device_file_corrections(
                        device_info
                    )
                )

                self.status.emit(
                    f"REFF files found: {reff_count}"
                )
                self.status.emit(
                    f"Screen videos found: {video_count}"
                )

                if not corrections:
                    self.status.emit(
                        "No affected files found for this device."
                    )
                    corrected_devices.append(device)
                    continue

                for correction in corrections:
                    current = datetime.fromtimestamp(
                        correction.current_timestamp
                    )
                    corrected = datetime.fromtimestamp(
                        correction.corrected_timestamp
                    )
                    self.status.emit(
                        f"  {PurePosixPath(correction.file_path).name}: "
                        f"{current:%d-%m-%Y %H:%M:%S} → "
                        f"{corrected:%d-%m-%Y %H:%M:%S}"
                    )

                self.status.emit(
                    f"Applying {len(corrections)} correction(s)..."
                )

                corrected_count = apply_file_time_corrections(
                    device,
                    corrections,
                )

                if corrected_count == len(corrections):
                    self.status.emit(
                        f"✓ {device.name}: "
                        f"{corrected_count} file(s) corrected."
                    )
                    corrected_devices.append(device)
                else:
                    self.status.emit(
                        f"✗ {device.name}: "
                        f"{corrected_count} of {len(corrections)} "
                        "file(s) corrected."
                    )
                    self.status.emit(
                        "Device will be skipped during extraction."
                    )

            self.status.emit("")
            self.status.emit(
                "⚠ Android clocks are still incorrect. "
                "Correct the device date/time manually after extraction."
            )

            self.finished.emit(corrected_devices)

        except Exception as error:
            self.failed.emit(str(error))


class ExtractionWorker(QObject):
    """Run REFF extraction and grouping."""

    status = Signal(str)
    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        devices: list[AndroidDevice],
        include_videos: bool,
    ) -> None:
        super().__init__()
        self.devices = devices
        self.include_videos = include_videos

    def run(self) -> None:
        """Run the existing extraction backend for selected devices."""

        try:
            create_output_directory()
            next_flight_number = get_next_flight_number()

            copied_reff_files = 0
            copied_videos = 0
            flights: list[Flight] = []
            warnings: list[GroupingWarning] = []

            total = len(self.devices)

            for index, device in enumerate(
                self.devices,
                start=1,
            ):
                result = process_device(
                    device,
                    include_videos=self.include_videos,
                    status_callback=self.status.emit,
                )

                copied_reff_files += result.reff_files
                copied_videos += result.videos

                self.progress.emit(
                    index,
                    total,
                )

            self.status.emit("")
            self.status.emit("Grouping REFF files into flights...")

            reff_grouping_result = group_files_into_flights(
                starting_flight_number=next_flight_number,
            )

            flights = reff_grouping_result.flights

            if self.include_videos:
                self.status.emit(
                    "Grouping screen videos into flights..."
                )

                video_grouping_result = group_videos_into_flights(
                    flights=reff_grouping_result.flights,
                    standalone_reffs=(
                        reff_grouping_result.standalone_reffs
                    ),
                    starting_flight_number=(
                        reff_grouping_result.next_flight_number
                    ),
                )

                flights = video_grouping_result.flights
                warnings = video_grouping_result.warnings

            self.status.emit("✓ Extraction completed successfully")

            self.finished.emit(
                {
                    "flights": flights,
                    "warnings": warnings,
                    "copied_reff_files": copied_reff_files,
                    "copied_videos": copied_videos,
                    "include_videos": self.include_videos,
                    "device_types": tuple(
                        device.file_prefix
                        for device in self.devices
                    ),
                    "destination": LOCAL_DUMP_DIR,
                    "transfer_verb": get_transfer_verb(),
                }
            )

        except Exception as error:
            self.failed.emit(str(error))


class ReffExtractorPage(QWidget):
    """Desktop interface for REFF and screen-video extraction."""

    def __init__(self) -> None:
        super().__init__()

        self.devices: list[AndroidDevice] = []
        self.time_info: list[DeviceTimeInfo] = []
        self.incorrect_devices: list[DeviceTimeInfo] = []
        self.devices_to_process: list[AndroidDevice] = []
        self.include_videos = False

        self.time_thread: QThread | None = None
        self.time_worker: DeviceTimeWorker | None = None
        self.correction_thread: QThread | None = None
        self.correction_worker: TimeCorrectionWorker | None = None
        self.extraction_thread: QThread | None = None
        self.extraction_worker: ExtractionWorker | None = None

        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        """Build the extraction page."""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(16)

        title = QLabel("REFF & Video Extractor")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Extract today's REFF files, optionally include screen videos, "
            "correct wrong file times, and group everything into flights."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(8)

        mode_row = QHBoxLayout()

        mode_label = QLabel("Extraction mode")
        mode_label.setObjectName("sectionTitle")

        self.reff_only_button = QPushButton("REFF Only")
        self.reff_only_button.setObjectName("modeButton")
        self.reff_only_button.setCheckable(True)
        self.reff_only_button.setChecked(True)
        self.reff_only_button.clicked.connect(
            lambda: self._select_mode(False)
        )

        self.reff_video_button = QPushButton(
            "REFF & Screen Videos"
        )
        self.reff_video_button.setObjectName("modeButton")
        self.reff_video_button.setCheckable(True)
        self.reff_video_button.clicked.connect(
            lambda: self._select_mode(True)
        )

        mode_row.addWidget(mode_label)
        mode_row.addStretch()
        mode_row.addWidget(self.reff_only_button)
        mode_row.addWidget(self.reff_video_button)

        root.addLayout(mode_row)

        top = QHBoxLayout()
        top.setSpacing(16)

        time_card = QFrame()
        time_card.setObjectName("workflowCard")
        time_layout = QVBoxLayout(time_card)
        time_layout.setContentsMargins(22, 20, 22, 20)
        time_layout.setSpacing(12)

        time_header = QHBoxLayout()

        time_title = QLabel("Device Time Status")
        time_title.setObjectName("sectionTitle")

        self.time_status = QLabel("Checking...")
        self.time_status.setObjectName("statusPill")

        time_header.addWidget(time_title)
        time_header.addStretch()
        time_header.addWidget(self.time_status)

        self.time_table = QTableWidget()
        self.time_table.setObjectName("dataTable")
        self.time_table.setColumnCount(4)
        self.time_table.setHorizontalHeaderLabels(
            [
                "Device",
                "Device Time",
                "Difference",
                "Status",
            ]
        )
        self.time_table.horizontalHeader().setStretchLastSection(True)
        self.time_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.time_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )

        time_buttons = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(
            self.refresh_devices
        )

        self.skip_bad_time_button = QPushButton(
            "Skip Incorrect Devices"
        )
        self.skip_bad_time_button.setObjectName("secondaryButton")
        self.skip_bad_time_button.hide()
        self.skip_bad_time_button.clicked.connect(
            self._skip_incorrect_devices
        )

        self.correct_time_button = QPushButton(
            "Correct Affected Files"
        )
        self.correct_time_button.setObjectName("primaryButton")
        self.correct_time_button.hide()
        self.correct_time_button.clicked.connect(
            self._correct_times
        )

        time_buttons.addWidget(self.refresh_button)
        time_buttons.addStretch()
        time_buttons.addWidget(self.skip_bad_time_button)
        time_buttons.addWidget(self.correct_time_button)

        time_layout.addLayout(time_header)
        time_layout.addWidget(self.time_table)
        time_layout.addLayout(time_buttons)

        activity_card = QFrame()
        activity_card.setObjectName("workflowCard")
        activity_layout = QVBoxLayout(activity_card)
        activity_layout.setContentsMargins(22, 20, 22, 20)
        activity_layout.setSpacing(12)

        activity_header = QHBoxLayout()

        activity_title = QLabel("Extraction Activity")
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
        self.progress.setFormat("Device %v of %m")

        self.log = QPlainTextEdit()
        self.log.setObjectName("installLog")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText(
            "Extraction and transfer activity will appear here..."
        )

        self.extract_button = QPushButton("Start Extraction")
        self.extract_button.setObjectName("primaryButton")
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(
            self.start_extraction
        )

        activity_layout.addLayout(activity_header)
        activity_layout.addWidget(self.progress)
        activity_layout.addWidget(self.log, stretch=1)
        activity_layout.addWidget(self.extract_button)

        top.addWidget(time_card, stretch=1)
        top.addWidget(activity_card, stretch=1)

        root.addLayout(top, stretch=1)

        results_card = QFrame()
        results_card.setObjectName("workflowCard")
        results_layout = QVBoxLayout(results_card)
        results_layout.setContentsMargins(22, 20, 22, 20)
        results_layout.setSpacing(12)

        results_header = QHBoxLayout()

        results_title = QLabel("Flights & Results")
        results_title.setObjectName("sectionTitle")

        self.results_summary = QLabel(
            "Run an extraction to see grouped flights."
        )
        self.results_summary.setObjectName("mutedText")

        results_header.addWidget(results_title)
        results_header.addStretch()
        results_header.addWidget(self.results_summary)

        self.flight_table = QTableWidget()
        self.flight_table.setObjectName("dataTable")
        self.flight_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.flight_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )

        results_layout.addLayout(results_header)
        results_layout.addWidget(self.flight_table)

        root.addWidget(results_card, stretch=1)

    def _select_mode(self, include_videos: bool) -> None:
        """Select REFF-only or REFF-and-videos mode."""

        self.include_videos = include_videos
        self.reff_only_button.setChecked(
            not include_videos
        )
        self.reff_video_button.setChecked(
            include_videos
        )

    def refresh_devices(self) -> None:
        """Refresh connected devices and their clock status."""

        if self.time_thread is not None and self.time_thread.isRunning():
            return

        self.refresh_button.setEnabled(False)
        self.extract_button.setEnabled(False)
        self.time_status.setText("Checking")
        self.log.clear()

        self.time_thread = QThread()
        self.time_worker = DeviceTimeWorker()
        self.time_worker.moveToThread(
            self.time_thread
        )

        self.time_thread.started.connect(
            self.time_worker.run
        )
        self.time_worker.status.connect(
            self._append_log
        )
        self.time_worker.finished.connect(
            self._show_time_status
        )
        self.time_worker.failed.connect(
            self._time_failed
        )
        self.time_worker.finished.connect(
            self.time_thread.quit
        )
        self.time_worker.failed.connect(
            self.time_thread.quit
        )
        self.time_thread.finished.connect(
            self._cleanup_time_thread
        )

        self.time_thread.start()

    def _show_time_status(
        self,
        devices: list[AndroidDevice],
        time_info: list[DeviceTimeInfo],
        incorrect: list[DeviceTimeInfo],
    ) -> None:
        """Render device clock information."""

        self.devices = devices
        self.time_info = time_info
        self.incorrect_devices = incorrect

        info_by_serial = {
            item.device.serial: item
            for item in time_info
        }

        self.time_table.setRowCount(
            len(devices)
        )

        for row, device in enumerate(devices):
            info = info_by_serial.get(
                device.serial
            )

            self.time_table.setItem(
                row,
                0,
                QTableWidgetItem(device.name),
            )

            if info is None:
                values = (
                    "Unavailable",
                    "-",
                    "Could not read clock",
                )
            else:
                values = (
                    info.device_datetime.strftime(
                        "%d-%m-%Y %H:%M:%S"
                    ),
                    format_time_difference(
                        info.difference_seconds
                    ),
                    "Needs Fix"
                    if info.needs_fix
                    else "✓ OK",
                )

            for column, value in enumerate(
                values,
                start=1,
            ):
                self.time_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

        self.time_table.resizeColumnsToContents()

        if not devices:
            self.time_status.setText("0 devices")
            self.devices_to_process = []
            self.extract_button.setEnabled(False)
            return

        if incorrect:
            self.time_status.setText(
                f"{len(incorrect)} need fix"
            )
            self.correct_time_button.show()
            self.skip_bad_time_button.show()
            self.devices_to_process = []
            self.extract_button.setEnabled(False)

            self._append_log("")
            self._append_log(
                f"⚠ {len(incorrect)} device(s) have an incorrect clock."
            )
        else:
            self.time_status.setText("✓ Ready")
            self.correct_time_button.hide()
            self.skip_bad_time_button.hide()
            self.devices_to_process = devices
            self.extract_button.setEnabled(True)

    def _skip_incorrect_devices(self) -> None:
        """Continue using only devices with acceptable clocks."""

        self.devices_to_process = get_devices_with_correct_time(
            self.devices,
            self.incorrect_devices,
        )

        self.correct_time_button.hide()
        self.skip_bad_time_button.hide()
        self.time_status.setText("Incorrect skipped")

        self._append_log(
            "Continuing without devices that have incorrect clocks."
        )

        self.extract_button.setEnabled(
            bool(self.devices_to_process)
        )

    def _correct_times(self) -> None:
        """Correct affected files before extraction."""

        if (
            self.correction_thread is not None
            and self.correction_thread.isRunning()
        ):
            return

        self.correct_time_button.setEnabled(False)
        self.skip_bad_time_button.setEnabled(False)
        self.activity_status.setText("Correcting")

        self.correction_thread = QThread()
        self.correction_worker = TimeCorrectionWorker(
            self.incorrect_devices
        )
        self.correction_worker.moveToThread(
            self.correction_thread
        )

        self.correction_thread.started.connect(
            self.correction_worker.run
        )
        self.correction_worker.status.connect(
            self._append_log
        )
        self.correction_worker.finished.connect(
            self._corrections_finished
        )
        self.correction_worker.failed.connect(
            self._correction_failed
        )
        self.correction_worker.finished.connect(
            self.correction_thread.quit
        )
        self.correction_worker.failed.connect(
            self.correction_thread.quit
        )
        self.correction_thread.finished.connect(
            self._cleanup_correction_thread
        )

        self.correction_thread.start()

    def _corrections_finished(
        self,
        corrected_devices: list[AndroidDevice],
    ) -> None:
        """Continue with correct and successfully corrected devices."""

        correct_devices = get_devices_with_correct_time(
            self.devices,
            self.incorrect_devices,
        )

        self.devices_to_process = (
            correct_devices + corrected_devices
        )

        self.time_status.setText("Corrections applied")
        self.correct_time_button.hide()
        self.skip_bad_time_button.hide()
        self.activity_status.setText("Ready")
        self.extract_button.setEnabled(
            bool(self.devices_to_process)
        )

    def _correction_failed(self, message: str) -> None:
        """Display time-correction failure."""

        self._append_log(
            f"✗ Time correction failed: {message}"
        )
        self.activity_status.setText("Failed")

    def _cleanup_correction_thread(self) -> None:
        """Release time-correction worker references."""

        self.correction_worker = None
        self.correction_thread = None
        self.correct_time_button.setEnabled(True)
        self.skip_bad_time_button.setEnabled(True)

    def start_extraction(self) -> None:
        """Start REFF extraction in a worker thread."""

        if not self.devices_to_process:
            return

        if (
            self.extraction_thread is not None
            and self.extraction_thread.isRunning()
        ):
            return

        self.extract_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.reff_only_button.setEnabled(False)
        self.reff_video_button.setEnabled(False)

        total = len(self.devices_to_process)
        self.progress.setRange(
            0,
            max(total, 1),
        )
        self.progress.setValue(0)

        self.activity_status.setText("Extracting")
        self._append_log("")
        self._append_log(
            "Starting REFF & screen video extraction..."
            if self.include_videos
            else "Starting REFF extraction..."
        )

        self.extraction_thread = QThread()
        self.extraction_worker = ExtractionWorker(
            self.devices_to_process,
            self.include_videos,
        )
        self.extraction_worker.moveToThread(
            self.extraction_thread
        )

        self.extraction_thread.started.connect(
            self.extraction_worker.run
        )
        self.extraction_worker.status.connect(
            self._append_log
        )
        self.extraction_worker.progress.connect(
            self._update_progress
        )
        self.extraction_worker.finished.connect(
            self._show_results
        )
        self.extraction_worker.failed.connect(
            self._extraction_failed
        )
        self.extraction_worker.finished.connect(
            self.extraction_thread.quit
        )
        self.extraction_worker.failed.connect(
            self.extraction_thread.quit
        )
        self.extraction_thread.finished.connect(
            self._cleanup_extraction_thread
        )

        self.extraction_thread.start()

    def _update_progress(
        self,
        completed: int,
        total: int,
    ) -> None:
        """Update device extraction progress."""

        self.progress.setRange(
            0,
            max(total, 1),
        )
        self.progress.setValue(completed)

    def _show_results(self, result: dict) -> None:
        """Render flights, extraction totals, and grouping warnings."""

        flights: list[Flight] = result["flights"]
        warnings: list[GroupingWarning] = result["warnings"]
        device_types: tuple[str, ...] = result["device_types"]
        include_videos: bool = result["include_videos"]

        headers = [
            "Flight",
            *device_types,
        ]

        if include_videos:
            headers.append("Screen Videos")

        self.flight_table.setColumnCount(
            len(headers)
        )
        self.flight_table.setHorizontalHeaderLabels(
            headers
        )
        self.flight_table.setRowCount(
            len(flights)
        )

        for row, flight in enumerate(flights):
            values = [flight.name]

            for device_type in device_types:
                filenames = [
                    reff.filename
                    for reff in flight.reff_files
                    if reff.device_type.value == device_type
                ]
                values.append(
                    "\n".join(filenames)
                    if filenames
                    else "-"
                )

            if include_videos:
                video_names = [
                    video.filename
                    for video in flight.videos
                ]
                values.append(
                    "\n".join(video_names)
                    if video_names
                    else "-"
                )

            for column, value in enumerate(values):
                self.flight_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

        self.flight_table.resizeColumnsToContents()
        self.flight_table.resizeRowsToContents()
        self.flight_table.horizontalHeader().setStretchLastSection(
            True
        )

        transfer_verb = result["transfer_verb"].lower()

        summary_parts = [
            f"Flights: {len(flights)}",
            f"REFF {transfer_verb}: {result['copied_reff_files']}",
        ]

        if include_videos:
            summary_parts.append(
                f"Videos {transfer_verb}: {result['copied_videos']}"
            )

        if warnings:
            summary_parts.append(
                f"Warnings: {len(warnings)}"
            )

        self.results_summary.setText(
            "  •  ".join(summary_parts)
        )

        self._append_log("")
        self._append_log("Extraction Summary")
        self._append_log(
            f"Flight folders created: {len(flights)}"
        )
        self._append_log(
            f"REFF files {transfer_verb}: "
            f"{result['copied_reff_files']}"
        )

        if include_videos:
            self._append_log(
                f"Screen videos {transfer_verb}: "
                f"{result['copied_videos']}"
            )

        if warnings:
            self._append_log(
                f"Recording warnings: {len(warnings)}"
            )
            self._append_log("")
            self._append_log("Recording Warnings")

            for warning in warnings:
                self._append_log(
                    f"⚠ {warning.device_type.value} | "
                    f"{warning.filename} | "
                    f"{warning.flight_name or 'Standalone'} | "
                    f"{warning.message}"
                )

        self._append_log("")
        self._append_log(
            f"All files are located at: {result['destination']}"
        )

        self.activity_status.setText("✓ Completed")

    def _extraction_failed(self, message: str) -> None:
        """Display an extraction failure."""

        self._append_log(
            f"✗ Extraction failed: {message}"
        )
        self.activity_status.setText("Failed")

    def _cleanup_extraction_thread(self) -> None:
        """Release extraction worker references."""

        self.extraction_worker = None
        self.extraction_thread = None

        self.refresh_button.setEnabled(True)
        self.reff_only_button.setEnabled(True)
        self.reff_video_button.setEnabled(True)
        self.extract_button.setEnabled(
            bool(self.devices_to_process)
        )

    def _time_failed(self, message: str) -> None:
        """Display device/time detection failure."""

        self._append_log(
            f"✗ Device check failed: {message}"
        )
        self.time_status.setText("Failed")

    def _cleanup_time_thread(self) -> None:
        """Release device-time worker references."""

        self.time_worker = None
        self.time_thread = None
        self.refresh_button.setEnabled(True)

    def _append_log(self, message: str) -> None:
        """Append one extraction activity message."""

        self.log.appendPlainText(message)
