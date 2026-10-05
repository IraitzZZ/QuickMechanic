"""Pantalla de bienvenida animada durante el indexado inicial de coches."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QSplashScreen

from . import APP_NAME, theme
from .branding import brand_pixmap
from .i18n import tr


class LoadingSplash(QSplashScreen):
    def __init__(self) -> None:
        pixmap = QPixmap(500, 310)
        pixmap.fill(QColor(theme.BG))
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(500, 310)
        self._progress = 0
        self._message = tr("INICIALIZANDO TALLER")
        self._timer = QTimer(self)
        self._timer.setInterval(24)
        self._timer.timeout.connect(self._advance)
        self._timer.start()
        self.repaint()

    def update_status(self, message: str, progress: int) -> None:
        self._message = tr(message).upper()
        self._progress = max(self._progress, min(100, int(progress)))
        self.repaint()

    def _advance(self) -> None:
        if self._progress < 86:
            self._progress += 1
        self.repaint()

    def finish(self, main_window) -> None:
        self._timer.stop()
        super().finish(main_window)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.BG))
        painter.setBrush(QColor(theme.PANEL))
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

        painter.setPen(QPen(QColor(theme.ACCENT), 1.5))
        painter.drawLine(28, 20, 472, 20)
        painter.drawPixmap(198, 34, 104, 104, brand_pixmap(104))

        painter.setPen(QColor(theme.FG))
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setItalic(True)
        font.setPointSize(20)
        painter.setFont(font)
        painter.drawText(0, 151, self.width(), 32, Qt.AlignmentFlag.AlignCenter, APP_NAME.upper())

        painter.setPen(QColor(theme.MUTED))
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPointSize(9)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(font)
        painter.drawText(0, 184, self.width(), 20, Qt.AlignmentFlag.AlignCenter,
                         "SIM RACING VEHICLE ENGINEERING")
        painter.setPen(QColor(theme.ACCENT_LIGHT))
        painter.drawText(40, 234, 420, 18, Qt.AlignmentFlag.AlignLeft, self._message)

        bar = self.rect().adjusted(40, 263, -40, -30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.BG_ALT))
        painter.drawRoundedRect(bar, 4, 4)
        fill = bar.adjusted(2, 2, -2, -2)
        fill.setWidth(int(fill.width() * self._progress / 100))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawRoundedRect(fill, 3, 3)
        painter.end()
