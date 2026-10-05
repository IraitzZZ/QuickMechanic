"""Identidad visual de la aplicacion y recursos opcionales de marca."""
from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QSplashScreen

from . import APP_NAME, __version__, theme
from .i18n import tr


def logo_path() -> Path | None:
    """Busca icono.ico en el proyecto o junto al ejecutable empaquetado."""
    roots: list[Path] = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    roots.extend((Path(__file__).resolve().parent.parent, Path(sys.executable).resolve().parent))
    seen = set()
    for root in roots:
        candidate = root / "icono.ico"
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


@lru_cache(maxsize=12)
def brand_pixmap(size: int = 128) -> QPixmap:
    """Usa icono.ico del usuario; si falta, dibuja un emblema QM dorado vectorial."""
    source = logo_path()
    if source is not None:
        supplied = QPixmap(str(source))
        if not supplied.isNull():
            return supplied.scaled(
                size, size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 128.0
    painter.scale(scale, scale)

    path = QPainterPath()
    path.moveTo(36, 6)
    path.lineTo(92, 6)
    path.lineTo(122, 36)
    path.lineTo(122, 92)
    path.lineTo(92, 122)
    path.lineTo(36, 122)
    path.lineTo(6, 92)
    path.lineTo(6, 36)
    path.closeSubpath()
    painter.setPen(QPen(QColor(theme.ACCENT_DARK), 2.0))
    painter.setBrush(QColor(theme.PANEL))
    painter.drawPath(path)

    inner = QPainterPath()
    inner.moveTo(42, 17)
    inner.lineTo(86, 17)
    inner.lineTo(111, 42)
    inner.lineTo(111, 86)
    inner.lineTo(86, 111)
    inner.lineTo(42, 111)
    inner.lineTo(17, 86)
    inner.lineTo(17, 42)
    inner.closeSubpath()
    painter.setPen(QPen(QColor(theme.ACCENT), 2.4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(inner)

    painter.setPen(QColor(theme.ACCENT_LIGHT))
    font = QFont(theme.preferred_font_family())
    font.setBold(True)
    font.setItalic(True)
    font.setPointSize(39)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "QM")
    painter.setPen(QPen(QColor(theme.ACCENT), 2.4))
    painter.drawLine(43, 96, 85, 96)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    """Prioriza el icono personal del usuario y recurre al logo QM si falta."""
    path = logo_path()
    if path is not None:
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return QIcon(brand_pixmap(128))


class LoadingSplash(QSplashScreen):
    """Splash animado con progreso del escaneo y transiciones suaves de estado."""

    fadeFinished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(brand_pixmap(128), Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setFixedSize(460, 320)
        self._progress = 8.0
        self._status = tr("PREPARANDO BOX DIGITAL")
        self._pending_status = ""
        self._status_opacity = 1.0
        self._phase = 0.0
        self._finish_target = None

        self._progress_animation = QPropertyAnimation(self, b"displayProgress", self)
        self._progress_animation.setDuration(520)
        self._progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_animation.finished.connect(self._begin_finish_fade)
        self._status_animation = QPropertyAnimation(self, b"statusOpacity", self)
        self._status_animation.setDuration(210)
        self._status_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._status_animation.finished.connect(self._status_transition_finished)

        self._ticker = QTimer(self)
        self._ticker.setInterval(30)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start()

    @pyqtProperty(float)
    def displayProgress(self) -> float:  # noqa: N802 (API de Qt)
        return self._progress

    @displayProgress.setter
    def displayProgress(self, value: float) -> None:  # noqa: N802 (API de Qt)
        self._progress = max(0.0, min(100.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def statusOpacity(self) -> float:  # noqa: N802 (API de Qt)
        return self._status_opacity

    @statusOpacity.setter
    def statusOpacity(self, value: float) -> None:  # noqa: N802 (API de Qt)
        self._status_opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def set_status(self, message: str, progress: int | None = None) -> None:
        normalized = tr(message).upper()
        if normalized != self._status and normalized != self._pending_status:
            self._pending_status = normalized
            self._status_animation.stop()
            self._status_animation.setStartValue(self._status_opacity)
            self._status_animation.setEndValue(0.0)
            self._status_animation.start()
        if progress is not None:
            self._progress_animation.stop()
            self._progress_animation.setStartValue(self._progress)
            self._progress_animation.setEndValue(max(0, min(100, int(progress))))
            self._progress_animation.start()

    def _status_transition_finished(self) -> None:
        if self._status_opacity > 0.01:
            return
        if self._pending_status:
            self._status = self._pending_status
            self._pending_status = ""
        self._status_animation.setStartValue(0.0)
        self._status_animation.setEndValue(1.0)
        self._status_animation.start()

    def _tick(self) -> None:
        # El brillo y el emblema se animan; el porcentaje solo cambia con el progreso real.
        self._phase = (self._phase + 0.018) % 1.0
        self.update()

    def finish(self, main_window) -> None:
        self._ticker.stop()
        self._status_animation.stop()
        self._finish_target = main_window
        self._progress_animation.stop()
        self._progress_animation.setStartValue(self._progress)
        self._progress_animation.setEndValue(100.0)
        self._progress_animation.setDuration(300)
        self._progress_animation.start()

    def _begin_finish_fade(self) -> None:
        if self._finish_target is None:
            return
        self.setWindowOpacity(1.0)
        self._finish_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._finish_animation.setDuration(280)
        self._finish_animation.setStartValue(1.0)
        self._finish_animation.setEndValue(0.0)
        self._finish_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self._finish_animation.finished.connect(self._finish_after_fade)
        self._finish_animation.start()

    def _finish_after_fade(self) -> None:
        super().finish(self._finish_target)
        self.fadeFinished.emit()

    def drawContents(self, painter: QPainter) -> None:  # noqa: N802 (API de Qt)
        del painter  # el splash se compone entero en paintEvent

    def paintEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.BG))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.PANEL))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)
        painter.setPen(QPen(QColor(theme.ACCENT_DARK), 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)

        pulse = 0.97 + 0.03 * (0.5 + 0.5 * math.sin(self._phase * 6.28318))
        painter.save()
        painter.setOpacity(0.88 + 0.12 * pulse)
        painter.translate(self.width() / 2, 89)
        painter.scale(pulse, pulse)
        painter.drawPixmap(-64, -64, 128, 128, brand_pixmap(128))
        painter.restore()

        painter.setPen(QColor(theme.FG))
        title_font = QFont(theme.preferred_font_family())
        title_font.setBold(True)
        title_font.setPointSize(20)
        painter.setFont(title_font)
        painter.drawText(0, 166, self.width(), 30, Qt.AlignmentFlag.AlignCenter, APP_NAME.upper())

        painter.setPen(QColor(theme.MUTED))
        small_font = QFont(theme.preferred_font_family())
        small_font.setBold(True)
        small_font.setPointSize(8)
        small_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        painter.setFont(small_font)
        painter.drawText(0, 197, self.width(), 20, Qt.AlignmentFlag.AlignCenter, "VEHICLE ENGINEERING · ASSETTO CORSA")
        painter.setOpacity(self._status_opacity)
        painter.setPen(QColor(theme.ACCENT_LIGHT))
        painter.drawText(0, 240, self.width(), 18, Qt.AlignmentFlag.AlignCenter, self._status)
        painter.setOpacity(1.0)

        bar = self.rect().adjusted(44, 278, -44, -24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.BG))
        painter.drawRoundedRect(bar, 4, 4)
        fill = bar.adjusted(2, 2, -2, -2)
        fill.setWidth(int(fill.width() * self._progress / 100))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawRoundedRect(fill, 3, 3)
        if self._progress < 100:
            shimmer_x = int((bar.width() + 72) * self._phase) - 72 + bar.left()
            shimmer = QLinearGradient(shimmer_x, 0, shimmer_x + 72, 0)
            shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
            shimmer.setColorAt(0.5, QColor(theme.ACCENT_LIGHT))
            shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.save()
            painter.setClipRect(bar)
            painter.setBrush(shimmer)
            painter.drawRoundedRect(bar, 4, 4)
            painter.restore()
        painter.setPen(QColor(theme.MUTED))
        painter.setFont(QFont(theme.preferred_font_family(), 8))
        painter.drawText(bar, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f"{self._progress:.0f}%")
        painter.end()
