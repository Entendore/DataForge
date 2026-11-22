"""DataForge – PySide6 Desktop Application Entry Point."""

import sys
import os

# Ensure the app directory is in the Python path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from models import init_db, seed_data
from main_window import MainWindow, apply_base_theme


def main():
    # High DPI support
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("DataForge")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DataForge")

    # Apply dark theme
    apply_base_theme(app)

    # Initialize database and seed data
    init_db()
    seed_data()

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
