"""Piezas de interfaz compartidas por las pestanas.


Ademas de los controles de siempre (Panel, GridView, plot_widget...) aqui viven
las piezas del rediseño: pastillas de estado, tiles con los datos clave del coche
y el panel que enseña la previsualizacion de la skin elegida.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QDesktopServices,
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QScrollArea,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import skins
from . import theme
from .branding import brand_pixmap

__all__ = [
    "dspin",
    "ispin",
    "Panel",
    "note",
    "heading",
    "clear_layout",
    "GridView",
    "BrandMark",
    "Pill",
    "StatTile",
    "StatRow",
    "CarPreview",
    "section_rule",
]

PLACEHOLDER_SIZE = (520, 300)


# --------------------------------------------------------------- controles
def dspin(
    minimum: float,
    maximum: float,
    step: float = 0.01,
    decimals: int = 3,
    unit: str = "",
    tip: str = "",
) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setSingleStep(step)
    box.setDecimals(decimals)
    box.setKeyboardTracking(False)  # no aplicar mientras se escribe a medias
    box.setMinimumWidth(92)
    box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if unit:
        box.setSuffix(f" {unit}")
    if tip:
        box.setToolTip(tip)
    return box


def ispin(
    minimum: int,
    maximum: int,
    step: int = 1,
    unit: str = "",
    tip: str = "",
) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setSingleStep(step)
    box.setKeyboardTracking(False)
    box.setMinimumWidth(92)
    box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if unit:
        box.setSuffix(f" {unit}")
    if tip:
        box.setToolTip(tip)
    return box


class BrandMark(QLabel):
    """Marca de Quick Mechanic compartida con el icono de ventana y el splash."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 44)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPixmap(brand_pixmap(42))
        self.setToolTip("Quick Mechanic · Vehicle engineering")


class Pill(QLabel):
    """Etiqueta compacta tipo ``RWD`` o ``286 CV``."""

    def __init__(self, text: str = "", tone: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("pill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tone = tone
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        color = theme.TILE_TONES.get(tone, theme.MUTED)
        self.setStyleSheet(
            "QLabel#pill {"
            f" color: {color};"
            f" background: {theme.tint(color, 0.14)};"
            f" border: 1px solid {theme.tint(color, 0.45)};"
            "}"
        )


class StatTile(QFrame):
    """Numero grande con su etiqueta y unidad (los datos clave del coche)."""

    def __init__(
        self,
        title: str,
        unit: str = "",
        tone: str = "accent",
        tip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statTile")
        self._tone = tone
        self.setMinimumWidth(96)
        self.setMinimumHeight(66)
        if tip:
            self.setToolTip(tip)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 9)
        layout.setSpacing(2)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("statTitle")
        layout.addWidget(self.title_label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("statValue")
        row.addWidget(self.value_label)
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("statUnit")
        self.unit_label.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        self.unit_label.setContentsMargins(0, 0, 0, 3)
        row.addWidget(self.unit_label)
        row.addStretch(1)
        layout.addLayout(row)
        self.set_tone(tone)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        color = theme.TILE_TONES.get(tone, theme.ACCENT)
        self.setStyleSheet(f"QFrame#statTile {{ border-top: 3px solid {color}; }}")
        self.value_label.setStyleSheet(f"QLabel#statValue {{ color: {theme.FG}; }}")

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())


class StatRow(QWidget):
    """Fila de tiles con los datos mas importantes de la pestana."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self.tiles: dict[str, StatTile] = {}

    def add(
        self, key: str, title: str, unit: str = "", tone: str = "accent", tip: str = ""
    ) -> StatTile:
        tile = StatTile(title, unit, tone, tip)
        self.tiles[key] = tile
        self._layout.addWidget(tile, 1)
        return tile

    def set(self, key: str, text: str) -> None:
        tile = self.tiles.get(key)
        if tile is not None:
            tile.set_value(text)

    def clear_values(self) -> None:
        for tile in self.tiles.values():
            tile.set_value("—")


# ------------------------------------------------------------------ tarjetas
class Panel(QGroupBox):
    """Caja con titulo y filas 'etiqueta ... control unidad'."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 8, 12, 10)
        self._layout.setSpacing(5)

    def add(self, label: str, widget: QWidget, unit: str = "", tip: str = "") -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        text = QLabel(label)
        if tip:
            text.setToolTip(tip)
            widget.setToolTip(widget.toolTip() or tip)
        layout.addWidget(text)
        layout.addStretch(1)
        layout.addWidget(widget)
        if unit:
            unit_label = QLabel(unit)
            unit_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
            unit_label.setMinimumWidth(38)
            layout.addWidget(unit_label)
        self._layout.addWidget(row)
        return widget

    def add_widget(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_note(self, text: str, tone: str = "info") -> QLabel:
        label = note(text, tone)
        self._layout.addWidget(label)
        return label

    def add_separator(self) -> QLabel:
        rule = section_rule()
        self._layout.addWidget(rule)
        return rule

    def layout_box(self) -> QVBoxLayout:
        return self._layout


class GridView(QWidget):
    """Tabla de dos columnas (delantero / trasero) para comparar valores."""

    def __init__(self, left: str, right: str) -> None:
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(6)
        for column, text in enumerate((left, right), start=1):
            header = QLabel(text.upper())
            header.setStyleSheet(
                f"color: {theme.ACCENT}; font-weight: bold; font-size: 10px;"
                " letter-spacing: 1.2px;"
            )
            self.grid.addWidget(header, 0, column)
        self._row = 1

    def add_pair(
        self,
        label: str,
        left: QWidget,
        right: QWidget,
        unit: str = "",
        tip: str = "",
    ) -> None:
        text = QLabel(label)
        if tip:
            text.setToolTip(tip)
        self.grid.addWidget(text, self._row, 0)
        self.grid.addWidget(left, self._row, 1)
        self.grid.addWidget(right, self._row, 2)
        if unit:
            unit_label = QLabel(unit)
            unit_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
            self.grid.addWidget(unit_label, self._row, 3)
        self._row += 1


def section_rule() -> QLabel:
    """Linea fina para separar bloques dentro de una tarjeta."""
    rule = QLabel()
    rule.setObjectName("sectionRule")
    rule.setFixedHeight(1)
    return rule


def note(text: str, tone: str = "info") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {theme.TONE_COLORS.get(tone, theme.MUTED)};")
    return label


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {theme.FG}; font-size: 14px; font-weight: bold;")
    return label


def clear_layout(layout) -> None:
    """Vacia un layout borrando sus widgets (se usa al recargar un coche)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


# ------------------------------------------------- previsualizacion del coche
class CarPreview(QFrame):
    """Panel con la foto del coche (la preview de la skin) y su selector.

    AC guarda una imagen ``preview`` dentro de cada carpeta de skin; aqui se
    enseña la de la skin elegida y se recuerda cual tenia cada coche.
    """

    skinChanged = pyqtSignal(str)  # nombre de la carpeta de la skin elegida

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.badge = QLabel()
        self.badge.setObjectName("previewBadge")
        self.badge.setFixedSize(30, 30)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title = QLabel("Ningun coche seleccionado")
        self.title.setObjectName("previewTitle")
        self.title.setWordWrap(True)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("previewSubtitle")
        self.subtitle.setWordWrap(True)
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        head.addLayout(titles, 1)
        layout.addLayout(head)

        self.image_view = QScrollArea()
        self.image_view.setObjectName("previewViewport")
        self.image_view.setWidgetResizable(False)
        self.image_view.setFrameShape(QFrame.Shape.NoFrame)
        self.image_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.image_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.image = QLabel()
        self.image.setObjectName("previewArea")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(160, 130)
        self.image.setToolTip("Doble clic para abrir la imagen original")
        self.image.installEventFilter(self)
        self.image.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.image_view.setWidget(self.image)
        layout.addWidget(self.image_view, 1)

        zoom_row = QHBoxLayout()
        zoom_row.setContentsMargins(0, 0, 0, 0)
        zoom_label = QLabel("ZOOM")
        zoom_label.setObjectName("previewSubtitle")
        zoom_row.addWidget(zoom_label)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(100, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setSingleStep(10)
        self.zoom_slider.setPageStep(25)
        self.zoom_slider.setObjectName("zoomSlider")
        self.zoom_slider.setToolTip("Amplía la previsualización hasta el 200%")
        self.zoom_slider.valueChanged.connect(self._rescale)
        zoom_row.addWidget(self.zoom_slider, 1)
        self.zoom_value = QLabel("100%")
        self.zoom_value.setObjectName("previewSubtitle")
        self.zoom_value.setMinimumWidth(38)
        zoom_row.addWidget(self.zoom_value)
        self.zoom_button = QPushButton("⤢")
        self.zoom_button.setObjectName("iconButton")
        self.zoom_button.setToolTip("Abrir imagen de previsualización a tamaño completo")
        self.zoom_button.clicked.connect(self.open_full_image)
        zoom_row.addWidget(self.zoom_button)
        layout.addLayout(zoom_row)

        skins_row = QHBoxLayout()
        skins_row.setSpacing(6)
        self.skin_box = QComboBox()
        self.skin_box.setToolTip("Skins del coche (la imagen es la preview de cada una)")
        self.skin_box.currentIndexChanged.connect(self._on_skin_changed)
        skins_row.addWidget(self.skin_box, 1)
        self.skin_count = QLabel("")
        self.skin_count.setObjectName("previewSubtitle")
        skins_row.addWidget(self.skin_count, 0)
        layout.addLayout(skins_row)

        self.detail = QLabel("")
        self.detail.setObjectName("previewSubtitle")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)

        self._pixmaps: dict[str, QPixmap] = {}
        self._source: QPixmap | None = None
        self._skins: list[skins.Skin] = []
        self._loading = False
        self._folder: Path | None = None
        self._memory: dict[str, str] = {}
        self._placeholder_text = ""
        self.zoom_slider.setEnabled(False)
        self.zoom_value.setText("100%")
        self.zoom_button.setEnabled(False)

        self.clear()

    # ------------------------------------------------------------------ carga
    def load(
        self,
        car_folder: Path | str | None,
        title: str = "",
        subtitle: str = "",
        badge: Path | None = None,
        preferred_skin: str = "",
    ) -> None:
        """Enseña el coche de ``car_folder`` con su skin preferida."""
        self._loading = True
        try:
            self._folder = Path(car_folder) if car_folder else None
            self._skins = skins.list_skins(self._folder) if self._folder else []
            self.zoom_slider.setValue(100)
            self.zoom_value.setText("100%")
            self.zoom_value.setText("100%")
            self.title.setText(title or (self._folder.name if self._folder else "Ningun coche"))
            self.subtitle.setText(subtitle or self._default_subtitle())
            self._set_badge(badge)
            self._placeholder_text = self.title.text()

            remembered = ""
            if self._folder is not None:
                remembered = preferred_skin or self._memory.get(self._folder.name, "")
            self.skin_box.clear()
            for skin in self._skins:
                self.skin_box.addItem(skin.label, skin.name)
            self.skin_box.setEnabled(bool(self._skins))
            if self._skins:
                index = next(
                    (i for i, skin in enumerate(self._skins) if skin.name == remembered), 0
                )
                self.skin_box.setCurrentIndex(index)
                self.skin_count.setText(
                    f"{len(self._skins)} skin" + ("s" if len(self._skins) != 1 else "")
                )
            else:
                self.skin_count.setText("")
            self._apply_skin()
        finally:
            self._loading = False

    def clear(self) -> None:
        self._folder = None
        self._skins = []
        self._source = None
        self._loading = True
        try:
            self.skin_box.clear()
            self.skin_box.setEnabled(False)
        finally:
            self._loading = False
        self.skin_count.setText("")
        self.title.setText("Ningun coche seleccionado")
        self.subtitle.setText("Elige un coche de la lista para ver su foto")
        self.detail.setText("")
        self._set_badge(None)
        self._placeholder_text = ""
        self.zoom_slider.setValue(100)
        self.zoom_value.setText("100%")
        self.zoom_slider.setEnabled(False)
        self.zoom_button.setEnabled(False)
        self.image.setPixmap(QPixmap())
        self.image.resize(1, 1)
        self.image.setText("Sin previsualizacion")

    # ------------------------------------------------------------------ skins
    @property
    def current_skin(self) -> str:
        return self.skin_box.currentData() or ""

    def preferred_skin(self, car_name: str) -> str:
        return self._memory.get(car_name, "")

    def _current_skins_entry(self) -> skins.Skin | None:
        index = self.skin_box.currentIndex()
        if 0 <= index < len(self._skins):
            return self._skins[index]
        return None

    def _default_subtitle(self) -> str:
        if not self._skins:
            return "Sin carpeta skins/ (el mod no trae skins)"
        return ""

    def _on_skin_changed(self, _index: int) -> None:
        if self._loading or self._folder is None:
            return
        skin = self._current_skins_entry()
        if skin is not None:
            self._memory[self._folder.name] = skin.name
        self._apply_skin(notify=True)

    def _apply_skin(self, notify: bool = False) -> None:
        skin = self._current_skins_entry()
        preview = skin.preview if skin is not None else None
        if preview is None and self._folder is not None:
            preview = skins.find_preview(self._folder)  # preview suelta en la raiz del coche
        self._show_image(preview)
        self.zoom_slider.setEnabled(preview is not None)
        self.zoom_button.setEnabled(preview is not None)
        details = skin.details if skin is not None else []
        if skin is not None and not details:
            # sin equipo ni dorsal al menos se ve el nombre de la carpeta de la skin
            details = [skin.name]
        if skin is not None and not skin.has_preview:
            details.append("sin imagen preview")
        self.detail.setText(" · ".join(details))
        if notify and skin is not None:
            self.skinChanged.emit(skin.name)

    def _show_image(self, path: Path | None) -> None:
        self._source = self._pixmap_for(path)
        if self._source is None:
            self._source = self._placeholder(self._placeholder_text)
        self._rescale()

    def _pixmap_for(self, path: Path | None) -> QPixmap | None:
        if path is None:
            return None
        key = str(path)
        cached = self._pixmaps.get(key)
        if cached is not None:
            return cached if not cached.isNull() else None
        pixmap = QPixmap()
        try:
            loaded = pixmap.load(key)
        except Exception:  # pragma: no cover - imagen corrupta
            loaded = False
        result = pixmap if loaded and not pixmap.isNull() else None
        self._pixmaps[key] = result if result is not None else QPixmap()
        return result

    def _set_badge(self, path: Path | None) -> None:
        pixmap = self._pixmap_for(path)
        if pixmap is None:
            self.badge.clear()
            return
        self.badge.setPixmap(
            pixmap.scaled(
                self.badge.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self, _value: int = 0) -> None:
        if self._source is None:
            return
        if hasattr(self, "zoom_value"):
            self.zoom_value.setText(f"{self.zoom_slider.value()}%")
        area = self.image_view.viewport().size()
        if area.width() < 20 or area.height() < 20:
            return
        zoom = self.zoom_slider.value() / 100.0 if hasattr(self, "zoom_slider") else 1.0
        fit = self._source.scaled(
            area,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        target = fit.size() * zoom
        self.image.setPixmap(
            self._source.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.image.resize(target)
        self.image_view.horizontalScrollBar().setValue(
            max(0, (target.width() - area.width()) // 2)
        )
        self.image_view.verticalScrollBar().setValue(
            max(0, (target.height() - area.height()) // 2)
        )

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (API de Qt)
        if watched is self.image and event.type() == QEvent.Type.MouseButtonDblClick:
            self.open_full_image()
            return True
        return super().eventFilter(watched, event)

    def open_full_image(self) -> None:
        """Abre el archivo original de la preview en el visor del sistema."""
        skin = self._current_skins_entry()
        path = skin.preview if skin is not None else None
        if path is None and self._folder is not None:
            path = skins.find_preview(self._folder)
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------ marcador
    def _placeholder(self, text: str) -> QPixmap:
        """Imagen de relleno con aire racing cuando el coche no trae preview."""
        width, height = PLACEHOLDER_SIZE
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(theme.BG))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0.0, QColor(theme.PANEL_ALT))
        gradient.setColorAt(1.0, QColor("#0a0c10"))
        painter.fillRect(0, 0, width, height, QBrush(gradient))

        # franjas diagonales, como una livery
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme.tint(theme.ACCENT, 0.10))))
        for offset in range(-height, width + height, 54):
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(offset, height),
                        QPointF(offset + 20, height),
                        QPointF(offset + 20 + height, 0),
                        QPointF(offset + height, 0),
                    ]
                )
            )

        # banda de cuadros de meta abajo
        cell = 14
        for index in range(0, width // cell + 1):
            if index % 2 == 0:
                continue
            painter.setBrush(QBrush(QColor(theme.tint("#ffffff", 0.14))))
            painter.drawRect(index * cell, height - cell, cell, cell)

        # monograma y aviso
        monogram = self._monogram(text)
        painter.setPen(QColor(theme.ACCENT))
        font = QFont()
        font.setPointSize(58)
        font.setWeight(QFont.Weight.Black)
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(
            0, 0, width, height - 42, Qt.AlignmentFlag.AlignCenter, monogram
        )

        painter.setPen(QColor(theme.MUTED))
        font.setPointSize(9)
        font.setWeight(QFont.Weight.DemiBold)
        font.setItalic(False)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
        painter.setFont(font)
        painter.drawText(
            0,
            height - 40,
            width,
            30,
            Qt.AlignmentFlag.AlignCenter,
            "SIN PREVISUALIZACION",
        )
        painter.end()
        return pixmap

    @staticmethod
    def _monogram(text: str) -> str:
        """Iniciales del coche para la imagen de relleno: ``Nissan 350Z`` -> NI."""
        words = [word for word in text.replace("-", " ").replace("_", " ").split() if word[:1].isalnum()]
        if not words:
            return "AC"
        if len(words[0]) > 3:
            return words[0][:2].upper()
        if len(words) >= 2:
            return (words[0][:1] + words[1][:1]).upper()
        return words[0][:2].upper()
