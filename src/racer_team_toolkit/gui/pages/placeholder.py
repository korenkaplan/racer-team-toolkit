"""Temporary page used while GUI features are being migrated."""

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


class PlaceholderPage(QWidget):
    """Temporary feature page."""

    def __init__(
        self,
        title_text: str,
        description_text: str,
    ) -> None:
        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            40,
            36,
            40,
            36,
        )

        title = QLabel(title_text)
        title.setObjectName("pageTitle")

        description = QLabel(description_text)

        description.setObjectName("pageSubtitle")

        layout.addWidget(title)
        layout.addWidget(description)

        layout.addStretch()
