from PySide6.QtWidgets import (QFrame, QHBoxLayout, QVBoxLayout, QLabel, 
                             QPushButton, QProgressBar, QWidget)
from PySide6.QtCore import Qt, Signal

class QueueItemWidget(QFrame):
    move_up = Signal()
    move_down = Signal()
    remove = Signal()

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.setFixedHeight(95)
        
        # Modern Card Style
        self.setStyleSheet("""
            QFrame {
                background-color: #262626;
                border: 1px solid #333;
                border-radius: 10px;
            }
            QFrame:hover {
                background-color: #2d2d2d;
                border: 1px solid #444;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 4px;
                color: #ccc;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #383838;
                color: #fff;
            }
            QPushButton#btn_remove {
                font-size: 20px;
                color: #995555;
            }
            QPushButton#btn_remove:hover {
                background-color: #4a2020;
                color: #ff6b6b;
            }
        """)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 12, 10, 12)
        main_layout.setSpacing(10)
        
        # Left Info Area
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        
        self.title_label = QLabel(url)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.title_label.setWordWrap(False)
        self.title_label.setMaximumWidth(220)
        
        self.status_label = QLabel("Waiting...")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #1a1a1a; border-radius: 3px; border: none; }
            QProgressBar::chunk { 
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #00BCD4, stop:1 #00E5FF); 
                border-radius: 3px; 
            }
        """)
        self.progress_bar.setVisible(False)
        
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.progress_bar)
        main_layout.addLayout(info_layout, stretch=1)
        
        # Right Button Area
        btn_widget = QWidget()
        btn_widget.setFixedWidth(50)
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 5, 0)
        btn_layout.setSpacing(2)
        btn_widget.setStyleSheet("background: transparent; border: none;")
        btn_widget.raise_()  # Ensure buttons are on top
        
        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedSize(28, 24)
        self.btn_up.setCursor(Qt.PointingHandCursor)
        self.btn_up.clicked.connect(self.move_up.emit)
        
        self.btn_rm = QPushButton("×")
        self.btn_rm.setObjectName("btn_remove")
        self.btn_rm.setFixedSize(28, 24)
        self.btn_rm.setCursor(Qt.PointingHandCursor)
        self.btn_rm.clicked.connect(self.remove.emit)
        
        self.btn_down = QPushButton("▼")
        self.btn_down.setFixedSize(28, 24)
        self.btn_down.setCursor(Qt.PointingHandCursor)
        self.btn_down.clicked.connect(self.move_down.emit)
        
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_rm)
        btn_layout.addWidget(self.btn_down)
        
        main_layout.addWidget(btn_widget)

    def set_status(self, text, progress=None):
        self.status_label.setText(text)
        if progress is not None:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(int(progress))
        else:
            self.progress_bar.setVisible(False)
            
    def set_title(self, title):
        self.title_label.setText(title)
