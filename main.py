import sys
from PySide6.QtWidgets import QApplication
from ui import ProcessManagerApp
from utils import log

if __name__ == "__main__":
    log.info("Application starting.")
    app = QApplication(sys.argv)
    window = ProcessManagerApp()
    sys.exit(app.exec())
