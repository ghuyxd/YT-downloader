import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from core.utils import check_ffmpeg

def main():
    app = QApplication(sys.argv)
    
    # Check ffmpeg BEFORE starting GUI
    if not check_ffmpeg():
        QMessageBox.critical(
            None, 
            "FFmpeg Not Found",
            "FFmpeg is required but not found in your system PATH.\n\n"
            "Please install FFmpeg:\n"
            "• Windows (Scoop): scoop install ffmpeg\n"
            "• Windows (Chocolatey): choco install ffmpeg\n"
            "• Linux (Ubuntu/Debian): sudo apt install ffmpeg\n"
            "• Linux (Arch): sudo pacman -S ffmpeg\n"
            "• macOS: brew install ffmpeg\n\n"
            "After installation, restart the application."
        )
        sys.exit(1)
    
    from gui import MediaDownloaderGUI
    window = MediaDownloaderGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
