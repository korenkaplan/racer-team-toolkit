"""Home dashboard for Racer Team Toolkit."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from racer_team_toolkit.gui.widgets.device_panel import (
    DevicePanel,
)
from racer_team_toolkit.gui.widgets.tool_card import (
    ToolCard,
)


class HomePage(QWidget):
    """Main GUI dashboard."""

    page_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the home dashboard."""

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            40,
            36,
            40,
            36,
        )

        layout.setSpacing(8)

        title = QLabel("Racer Team Toolkit")
        title.setObjectName("pageTitle")

        subtitle = QLabel("Manage, deploy, extract, and analyze Racer Team data.")

        subtitle.setObjectName("pageSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addSpacing(28)

        cards_layout = QGridLayout()

        cards_layout.setHorizontalSpacing(16)
        cards_layout.setVerticalSpacing(16)

        cards = [
            (
                "Full Release Update",
                "Install APKs and update the Racer Groundlord JAR.",
                1,
            ),
            (
                "REFF & Video Extractor",
                "Extract and organize REFF files and screen recordings.",
                2,
            ),
            (
                "APK Installer",
                "Install APK files on connected Android devices.",
                3,
            ),
            (
                "JAR Management",
                "Upload and manage the Racer Groundlord JAR.",
                4,
            ),
            (
                "Extract IMU Recordings",
                "Download IMU CSV recordings from the server.",
                5,
            ),
            (
                "Folders Reset",
                "Reset testing folders to a known state.",
                6,
            ),
        ]

        for index, (
            card_title,
            description,
            page_index,
        ) in enumerate(cards):
            card = ToolCard(
                card_title,
                description,
            )

            card.clicked.connect(lambda page=page_index: self.page_requested.emit(page))

            row = index // 3
            column = index % 3

            cards_layout.addWidget(
                card,
                row,
                column,
            )

        layout.addLayout(cards_layout)

        layout.addSpacing(24)

        device_panel = DevicePanel()

        layout.addWidget(device_panel)
