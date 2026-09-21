"""Main desktop window for Racer Team Toolkit."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from racer_team_toolkit.gui.pages.apk_installer import ApkInstallerPage
from racer_team_toolkit.gui.pages.folders_reset import FoldersResetPage
from racer_team_toolkit.gui.pages.full_release import FullReleasePage
from racer_team_toolkit.gui.pages.home import HomePage
from racer_team_toolkit.gui.pages.imu_recordings import ImuRecordingsPage
from racer_team_toolkit.gui.pages.jar_management import JarManagementPage
from racer_team_toolkit.gui.pages.reff_extractor import ReffExtractorPage
from racer_team_toolkit.gui.style import APP_STYLESHEET
from racer_team_toolkit.gui.widgets.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Main Racer Team Toolkit desktop window."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Racer Team Toolkit")
        self.resize(1380, 860)
        self.setMinimumSize(1100, 720)

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

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, stretch=1)

        return container

    def _build_pages(self) -> None:
        """Create all functional GUI pages."""

        home_page = HomePage()

        self.pages.addWidget(home_page)
        self.pages.addWidget(FullReleasePage())
        self.pages.addWidget(ReffExtractorPage())
        self.pages.addWidget(ApkInstallerPage())
        self.pages.addWidget(JarManagementPage())
        self.pages.addWidget(ImuRecordingsPage())
        self.pages.addWidget(FoldersResetPage())

        home_page.page_requested.connect(self.show_page)

    def _connect_navigation(self) -> None:
        """Connect sidebar navigation."""

        self.sidebar.page_requested.connect(self.show_page)

    def show_page(self, index: int) -> None:
        """Display a page by index."""

        self.pages.setCurrentIndex(index)

        buttons = self.sidebar.button_group.buttons()

        if 0 <= index < len(buttons):
            buttons[index].setChecked(True)

    def _apply_theme(self) -> None:
        """Apply the shared Racer Team Toolkit theme."""

        self.setStyleSheet(APP_STYLESHEET)
