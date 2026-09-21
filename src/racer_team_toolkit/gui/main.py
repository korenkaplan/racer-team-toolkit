"""PySide6 entry point for Racer Team Toolkit."""

import sys

from PySide6.QtWidgets import QApplication

from racer_team_toolkit.gui.main_window import MainWindow


def main() -> None:
    """Run the Racer Team Toolkit desktop application."""

    app = QApplication(sys.argv)

    app.setApplicationName("Racer Team Toolkit")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
