"""Reusable tool card widget."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
)


class ToolCard(QFrame):
    """Clickable card representing one toolkit feature."""

    clicked = Signal()

    def __init__(
        self,
        title: str,
        description: str,
    ) -> None:
        super().__init__()

        self.setObjectName("toolCard")

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")

        description_label = QLabel(description)
        description_label.setObjectName("cardDescription")

        description_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(description_label)

        layout.addStretch()

    def mousePressEvent(self, event) -> None:
        """Emit clicked when the card is pressed."""

        self.clicked.emit()

        super().mousePressEvent(event)
