"""Graficas ligeras de Quick Mechanic (QPainter puro, sin dependencias).

Dos widgets compartidos por las pestanas de analisis:

* :class:`CurveEditor` — dibuja una curva y permite **arrastrar sus puntos** en
  vertical para editarla (curva de par, curva de frenada...). Nunca guarda por su
  cuenta: avisa con ``pointChanged`` y quien lo usa decide que escribir.
* :class:`LineChart` — varias series con leyenda, para ver la velocidad de cada
  marcha o comparar dos coches.

Los colores salen de :mod:`quickmechanic.theme`, asi que siguen el tema activo.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from . import theme
from .qt_i18n import QLabel

__all__ = ["CurveEditor", "LineChart", "Legend", "PALETTE"]

PADDING = (46, 14, 14, 26)  # izquierda, arriba, derecha, abajo

# Colores para series multiples: el tema es monocromo, asi que se juega con
# intensidades y con los dos tonos de acento.
PALETTE = (theme.ACCENT, theme.ACCENT_LIGHT, theme.INFO, theme.ACCENT_DARK, theme.FG, theme.MUTED)


class _Plot(QWidget):
    """Base con ejes, rejilla y conversion mundo <-> pantalla."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.x_min = 0.0
        self.x_max = 1.0
        self.y_min = 0.0
        self.y_max = 1.0
        self.x_label = ""
        self.y_label = ""
        self._left, self._top, self._right, self._bottom = PADDING

    # ------------------------------------------------------------ coordenadas
    def _plot_rect(self) -> QRectF:
        return QRectF(
            self._left,
            self._top,
            max(self.width() - self._left - self._right, 10),
            max(self.height() - self._top - self._bottom, 10),
        )

    def _to_screen(self, x: float, y: float) -> QPointF:
        rect = self._plot_rect()
        span_x = (self.x_max - self.x_min) or 1.0
        span_y = (self.y_max - self.y_min) or 1.0
        px = rect.left() + (x - self.x_min) / span_x * rect.width()
        py = rect.bottom() - (y - self.y_min) / span_y * rect.height()
        return QPointF(px, py)

    def _to_world(self, point: QPointF) -> tuple[float, float]:
        rect = self._plot_rect()
        span_x = (self.x_max - self.x_min) or 1.0
        span_y = (self.y_max - self.y_min) or 1.0
        x = self.x_min + (point.x() - rect.left()) / rect.width() * span_x
        y = self.y_min + (rect.bottom() - point.y()) / rect.height() * span_y
        return x, y

    def margins(self) -> tuple[int, int, int, int]:
        return self._left, self._top, self._right, self._bottom

    def set_margins(self, left: int, top: int, right: int, bottom: int) -> None:
        self._left, self._top, self._right, self._bottom = int(left), int(top), int(right), int(bottom)
        self.update()

    def set_range(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        if x_max <= x_min:
            x_max = x_min + 1.0
        if y_max <= y_min:
            y_max = y_min + 1.0
        self.x_min, self.x_max = float(x_min), float(x_max)
        self.y_min, self.y_max = float(y_min), float(y_max)
        self.update()

    # ---------------------------------------------------------------- pintado
    def _paint_frame(self, painter: QPainter, rows: int = 5, columns: int = 6) -> None:
        rect = self._plot_rect()
        painter.fillRect(rect, QColor(theme.tint(theme.PANEL, 0.5)))
        painter.setPen(QPen(QColor(theme.tint(theme.MUTED, 0.35)), 1))
        for index in range(rows + 1):
            y = rect.top() + rect.height() * index / rows
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        for index in range(columns + 1):
            x = rect.left() + rect.width() * index / columns
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        painter.setPen(QPen(QColor(theme.tint(theme.MUTED, 0.8)), 1))
        painter.drawRect(rect)

        font = QFont(painter.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        painter.setFont(font)
        painter.setPen(QColor(theme.MUTED))
        for index in range(rows + 1):
            value = self.y_max - (self.y_max - self.y_min) * index / rows
            y = rect.top() + rect.height() * index / rows
            painter.drawText(
                QRectF(0, y - 8, self._left - 6, 16),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                _short(value),
            )
        for index in range(columns + 1):
            value = self.x_min + (self.x_max - self.x_min) * index / columns
            x = rect.left() + rect.width() * index / columns
            painter.drawText(
                QRectF(x - 34, rect.bottom() + 3, 68, 16),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                _short(value),
            )
        if self.x_label:
            painter.drawText(
                QRectF(rect.left(), rect.bottom() + 12, rect.width(), 16),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                self.x_label,
            )
        if self.y_label:
            painter.save()
            painter.translate(10, rect.center().y())
            painter.rotate(-90)
            painter.drawText(
                QRectF(-rect.height() / 2, -6, rect.height(), 14),
                int(Qt.AlignmentFlag.AlignCenter),
                self.y_label,
            )
            painter.restore()


def _short(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k".replace(".0k", "k")
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


class CurveEditor(_Plot):
    """Curva editable arrastrando puntos (vertical)."""

    pointChanged = pyqtSignal(int, float)   # indice, nuevo valor
    editingFinished = pyqtSignal()
    hovered = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: list[tuple[float, float]] = []
        self._active: int | None = None
        self._hover: int | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.y_label = ""
        self.x_label = ""
        self.minimum = 0.0
        self.maximum = 1
        self.unit = ""

    # ------------------------------------------------------------------ datos
    def set_points(self, points, *, minimum: float = 0.0, maximum: float = 1e9) -> None:
        self._points = [(float(x), float(y)) for x, y in points]
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        if not self._points:
            self.set_range(0, 1, 0, 1)
            return
        xs = [x for x, _y in self._points]
        ys = [y for _x, y in self._points]
        low = min(ys)
        high = max(ys)
        margin = (high - low) * 0.15 or max(abs(high) * 0.1, 1.0)
        self.set_range(min(xs), max(xs), max(0.0, low - margin), high + margin)

    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def active_index(self) -> int | None:
        return self._hover if self._hover is not None else self._active

    def value_at(self, index: int) -> float | None:
        if 0 <= index < len(self._points):
            return self._points[index][1]
        return None

    # ------------------------------------------------------------- interaccion
    def _nearest(self, position: QPointF) -> int | None:
        best: tuple[float, int] | None = None
        for index, (x, y) in enumerate(self._points):
            screen = self._to_screen(x, y)
            distance = (screen.x() - position.x()) ** 2 + (screen.y() - position.y()) ** 2
            if best is None or distance < best[0]:
                best = (distance, index)
        if best is None:
            return None
        return best[1] if best[0] <= 24 ** 2 else None

    def mousePressEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        index = self._nearest(event.position())
        if index is None:
            return
        self._active = index
        self._apply(index, event.position())
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        index = self._nearest(event.position())
        if index != self._hover:
            self._hover = index
            self.hovered.emit(index if index is not None else -1)
        if self._active is not None:
            self._apply(self._active, event.position())
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._active is not None:
            self._active = None
            self.editingFinished.emit()
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = None
        self.hovered.emit(-1)
        self.update()

    def _apply(self, index: int, position: QPointF) -> None:
        _x, value = self._to_world(position)
        value = min(max(value, self.minimum), self.maximum)
        x, old = self._points[index]
        if abs(value - old) < 1e-9:
            return
        self._points[index] = (x, value)
        self.pointChanged.emit(index, value)

    # ---------------------------------------------------------------- pintado
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_frame(painter)
        if not self._points:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(self._plot_rect(), int(Qt.AlignmentFlag.AlignCenter), "sin datos")
            return
        path = QPainterPath()
        for index, (x, y) in enumerate(self._points):
            point = self._to_screen(x, y)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        painter.setPen(QPen(QColor(theme.ACCENT), 2))
        painter.drawPath(path)

        hover = self.active_index()
        for index, (x, y) in enumerate(self._points):
            point = self._to_screen(x, y)
            radius = 6.0 if index == hover else 3.4
            painter.setBrush(QColor(theme.ACCENT if index == hover else theme.tint(theme.ACCENT, 0.75)))
            painter.setPen(QPen(QColor(theme.BG), 1))
            painter.drawEllipse(point, radius, radius)
        if hover is not None and 0 <= hover < len(self._points):
            x, y = self._points[hover]
            painter.setPen(QColor(theme.FG))
            text = f"{x:.0f} → {y:.1f} {self.unit}".strip()
            screen = self._to_screen(x, y)
            painter.drawText(QPointF(screen.x() + 10, screen.y() - 8), text)


class LineChart(_Plot):
    """Varias series de lineas, con puntos marcados y leyenda simple."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._series: list[dict] = []
        self.y_label = "km/h"
        self.x_label = "rpm"

    def set_series(self, series) -> None:
        """``series``: [{'label', 'points': [(x, y)], 'color'?, 'markers': [x]}]"""
        self._series = []
        xs: list[float] = []
        ys: list[float] = []
        for item in series:
            points = [(float(x), float(y)) for x, y in item.get("points", [])]
            if not points:
                continue
            self._series.append(
                {
                    "label": str(item.get("label", "")),
                    "points": points,
                    "color": str(item.get("color", theme.ACCENT)),
                    "markers": [float(value) for value in item.get("markers", [])],
                }
            )
            xs.extend(x for x, _y in points)
            ys.extend(y for _x, y in points)
        if not xs:
            self.set_range(0, 1, 0, 1)
            return
        self.set_range(min(xs), max(xs), 0.0, max(ys) * 1.08)

    def series(self) -> list[dict]:
        return list(self._series)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_frame(painter)
        if not self._series:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(self._plot_rect(), int(Qt.AlignmentFlag.AlignCenter), "sin datos")
            return
        for item in self._series:
            path = QPainterPath()
            for index, (x, y) in enumerate(item["points"]):
                point = self._to_screen(x, y)
                if index == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            painter.setPen(QPen(QColor(item["color"]), 2))
            painter.drawPath(path)
            for marker in item["markers"]:
                start = self._to_screen(marker, self.y_min)
                end = self._to_screen(marker, self.y_max)
                painter.setPen(QPen(QColor(theme.tint(item["color"], 0.5)), 1, Qt.PenStyle.DashLine))
                painter.drawLine(start, end)
            for index, (x, y) in enumerate(item["points"]):
                point = self._to_screen(x, y)
                painter.setBrush(QColor(item["color"]))
                painter.setPen(QPen(QColor(theme.BG), 1))
                painter.drawEllipse(point, 3.0 if index else 4.0, 3.0 if index else 4.0)

    def legend(self) -> list[tuple[str, str]]:
        return [(item["label"], item["color"]) for item in self._series]


class Legend(QLabel):
    """Leyenda de colores: se rellena con ``set_entries``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setObjectName("previewSubtitle")
        self._entries: list[tuple[str, str]] = []

    def set_entries(self, entries) -> None:
        self._entries = [(str(label), str(color)) for label, color in entries]
        self.setText("   ".join(
            f"<span style='color:{color}'>■</span> {label}" for label, color in self._entries
        ))

    def entries(self) -> list[tuple[str, str]]:
        return list(self._entries)
