import sys
from PySide6.QtWidgets import QApplication
from gui import MediaDownloaderGUI

def main():
    app = QApplication(sys.argv)
    window = MediaDownloaderGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
