"""Main desktop window for Racer Team Toolkit."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from racer_team_toolkit.gui.pages.apk_installer import (
    ApkInstallerPage,
)
from racer_team_toolkit.gui.pages.home import (
    HomePage,
)
from racer_team_toolkit.gui.pages.placeholder import (
    PlaceholderPage,
)
from racer_team_toolkit.gui.widgets.sidebar import (
    Sidebar,
)


class MainWindow(QMainWindow):
    """Main Racer Team Toolkit desktop window."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Racer Team Toolkit")

        self.resize(
            1250,
            780,
        )

        self.pages = QStackedWidget()

        self.sidebar = Sidebar()

        self.setCentralWidget(self._build_window())

        self._build_pages()
        self._connect_navigation()
        self._apply_theme()

    def _build_window(self) -> QWidget:
        """Build the main desktop layout."""

        container = QWidget()

        layout = QHBoxLayout(container)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(0)

        layout.addWidget(self.sidebar)

        layout.addWidget(
            self.pages,
            stretch=1,
        )

        return container

    def _build_pages(self) -> None:
        """Create all GUI pages."""

        home_page = HomePage()

        self.pages.addWidget(home_page)

        self.pages.addWidget(
            PlaceholderPage(
                "Full Release Update",
                "Install APKs and update the Racer Groundlord JAR.",
            )
        )

        self.pages.addWidget(
            PlaceholderPage(
                "REFF & Video Extractor",
                "Extract and organize REFF files and screen recordings.",
            )
        )

        self.pages.addWidget(
            ApkInstallerPage()
        )

        self.pages.addWidget(
            PlaceholderPage(
                "JAR Management",
                "Upload and manage the Racer Groundlord JAR.",
            )
        )

        self.pages.addWidget(
            PlaceholderPage(
                "Extract IMU Recordings",
                "Download IMU recordings from the server.",
            )
        )

        self.pages.addWidget(
            PlaceholderPage(
                "Folders Reset",
                "Reset testing folders to a known state.",
            )
        )

        home_page.page_requested.connect(self.show_page)

    def _connect_navigation(self) -> None:
        """Connect sidebar navigation."""

        self.sidebar.page_requested.connect(self.show_page)

    def show_page(
        self,
        index: int,
    ) -> None:
        """Display a page by index."""

        self.pages.setCurrentIndex(index)

        buttons = self.sidebar.button_group.buttons()

        if 0 <= index < len(buttons):
            buttons[index].setChecked(True)

    def _apply_theme(self) -> None:
        """Apply the Racer Team Toolkit theme."""

        self.setStyleSheet(
            """
            #devicePanel {
    background-color: #172333;
    border: 1px solid #26384d;
    border-radius: 12px;
}

#panelTitle {
    font-size: 17px;
    font-weight: 700;
    color: #ffffff;
    background-color: transparent;
}

#panelStatus {
    font-size: 12px;
    color: #8fa0b3;
    background-color: transparent;
}

#deviceRow {
    background-color: #111c29;
    border: 1px solid #26384d;
    border-radius: 8px;
}

#deviceName {
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
    background-color: transparent;
}

#deviceSerial {
    font-size: 11px;
    color: #7f90a3;
    background-color: transparent;
}

#deviceConnected {
    color: #45d483;
    font-size: 12px;
    background-color: transparent;
}

#emptyState {
    color: #8393a6;
    background-color: transparent;
    padding: 16px;
}

#errorText {
    color: #ff6b6b;
    background-color: transparent;
}

#secondaryButton {
    background-color: #1b2b3e;
    border: 1px solid #30465f;
    border-radius: 7px;
    padding: 9px 14px;
    color: #d8e2ed;
}

#secondaryButton:hover {
    background-color: #22364c;
    border-color: #397ccb;
}

#primaryButton {
    background-color: #1f6feb;
    border: 1px solid #2f81f7;
    border-radius: 7px;
    padding: 10px 18px;
    color: #ffffff;
    font-weight: 600;
}

#primaryButton:hover {
    background-color: #2f81f7;
}

#primaryButton:disabled {
    background-color: #243244;
    border-color: #304052;
    color: #6f8194;
}

#workflowCard {
    background-color: #172333;
    border: 1px solid #26384d;
    border-radius: 12px;
}

#workflowSteps {
    background-color: transparent;
    color: #8192a6;
    font-size: 12px;
}

#sectionTitle {
    background-color: transparent;
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
}

#mutedText {
    background-color: transparent;
    color: #8fa0b3;
    font-size: 12px;
}

#selectionRow {
    background-color: #111c29;
    border: 1px solid #26384d;
    border-radius: 8px;
}

#successText {
    background-color: transparent;
    color: #45d483;
}

#warningText {
    background-color: transparent;
    color: #eab308;
}

#missingText {
    background-color: transparent;
    color: #ff6b6b;
    font-weight: 600;
}

#folderCombo {
    background-color: #111c29;
    border: 1px solid #30465f;
    border-radius: 7px;
    padding: 9px 12px;
    color: #e8eef5;
}

#installProgress {
    background-color: #111c29;
    border: 1px solid #30465f;
    border-radius: 7px;
    min-height: 20px;
    text-align: center;
}

#installProgress::chunk {
    background-color: #1f6feb;
    border-radius: 6px;
}
            QMainWindow {
                background-color: #0f1720;
            }

            QWidget {
                background-color: #111b27;
                color: #e8eef5;
                font-family: Arial;
                font-size: 14px;
            }

            #sidebar {
                background-color: #101923;
                border-right: 1px solid #263548;
            }

            #sidebarTitle {
                font-size: 18px;
                font-weight: 700;
                color: #ffffff;
            }

            #sidebarSubtitle {
                color: #8594a6;
                font-size: 12px;
            }

            #sidebarButton {
                background-color: transparent;
                border: none;
                border-radius: 7px;
                padding: 12px;
                text-align: left;
                color: #bcc8d6;
            }

            #sidebarButton:hover {
                background-color: #19283a;
                color: #ffffff;
            }

            #sidebarButton:checked {
                background-color: #173758;
                color: #ffffff;
                font-weight: 600;
            }

            #pageTitle {
                font-size: 30px;
                font-weight: 700;
                color: #ffffff;
            }

            #pageSubtitle {
                font-size: 15px;
                color: #8fa0b3;
            }

            #toolCard {
                background-color: #172333;
                border: 1px solid #26384d;
                border-radius: 12px;
                min-height: 120px;
            }

            #toolCard:hover {
                background-color: #1b2b3e;
                border: 1px solid #3479c9;
            }

            #cardTitle {
                font-size: 17px;
                font-weight: 700;
                color: #ffffff;
                background-color: transparent;
            }

            #cardDescription {
                font-size: 13px;
                color: #8fa0b3;
                background-color: transparent;
            }

            #versionLabel {
                color: #637387;
                font-size: 11px;
            }
            """
        )
