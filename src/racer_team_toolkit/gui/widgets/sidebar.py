"""Sidebar navigation for the Racer Team Toolkit GUI."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class Sidebar(QFrame):
    """Main application navigation sidebar."""

    page_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("sidebar")
        self.setFixedWidth(240)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build sidebar contents."""

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            20,
            24,
            20,
            24,
        )

        layout.setSpacing(8)

        title = QLabel("Racer Team Toolkit")
        title.setObjectName("sidebarTitle")

        subtitle = QLabel("Tools for a faster team")
        subtitle.setObjectName("sidebarSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addSpacing(24)

        menu_items = [
            "Home",
            "Full Release Update",
            "REFF & Video Extractor",
            "APK Installer",
            "JAR Management",
            "Extract IMU Recordings",
            "Folders Reset",
        ]

        for index, label in enumerate(menu_items):
            button = QPushButton(label)

            button.setObjectName("sidebarButton")
            button.setCheckable(True)

            button.clicked.connect(lambda checked=False, page=index: self.page_requested.emit(page))

            self.button_group.addButton(button)

            layout.addWidget(button)

            if index == 0:
                button.setChecked(True)

        layout.addStretch()

        version = QLabel("Racer Team Toolkit\nDevelopment")

        version.setObjectName("versionLabel")

        layout.addWidget(version)
