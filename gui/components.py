from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush

class GradientButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._hover = False
        
    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        gradient = QLinearGradient(0, 0, self.width(), 0)
        if self.isEnabled():
            if self._hover:
                gradient.setColorAt(0, QColor("#00E5FF"))
                gradient.setColorAt(1, QColor("#00B8D4"))
            else:
                gradient.setColorAt(0, QColor("#00BCD4"))
                gradient.setColorAt(1, QColor("#00838F"))
        else:
            gradient.setColorAt(0, QColor("#555"))
            gradient.setColorAt(1, QColor("#555"))
            
        rect = self.rect()
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 4, 4)
        
        painter.setPen(Qt.black if self.isEnabled() else Qt.white)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text())
