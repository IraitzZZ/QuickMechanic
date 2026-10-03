"""Tema fijo de Quick Mechanic: negro grafito, gris tecnico y oro satinado.

La paleta se inspira en instrumentacion de motorsport de lujo: superficies
negras, separadores grafito y detalles dorados reservados para acciones y datos
importantes. Los estados conservan jerarquia mediante tonos de la misma familia;
el tema no permite acentos alternativos ni preferencias cromaticas heredadas.

Los pocos iconos que hacen falta (flechas de los QSpinBox, la del desplegable y
el visto del checkbox) se dibujan una vez y se guardan como PNG en la carpeta de
configuracion de la app: Qt, cuando se le aplica una hoja de estilo, deja de
pintar las flechas nativas de esos controles y hay que darle una imagen.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

__all__ = [
    "BG",
    "BG_ALT",
    "PANEL",
    "PANEL_ALT",
    "BORDER",
    "FG",
    "MUTED",
    "ACCENT",
    "ACCENT_LIGHT",
    "ACCENT_DARK",
    "TILE_TONES",
    "OK",
    "WARN",
    "DANGER",
    "INFO",
    "TONE_COLORS",
    "FONT_STACK",
    "preferred_font_family",
    "QSS",
    "_TILE_TONES_BASE",
    "stylesheet",
    "tint",
    "assets_dir",
    "ensure_assets",
    "apply",
]

# --------------------------------------------------------------------- paleta
BG = "#0b0c0e"           # fondo carbón
BG_ALT = "#111316"
PANEL = "#17191c"        # superficies de carbono
PANEL_ALT = "#202327"    # campos de formulario
RAISED = "#292c30"       # botones elevados
RAISED_BORDER = "#3b3f44"
RAISED_HOVER = "#34383d"
BORDER = "#303438"
FG = "#ece9e2"
MUTED = "#92918c"

ACCENT = "#c6a45a"       # oro champagne
ACCENT_LIGHT = "#e4ca83"
ACCENT_DARK = "#735d32"
GOLD = ACCENT
GOLD_LIGHT = ACCENT_LIGHT
GOLD_DARK = ACCENT_DARK

OK = ACCENT_LIGHT
WARN = ACCENT
DANGER = "#d7c9a2"
INFO = "#a9a79f"

TONE_COLORS = {"ok": OK, "aviso": WARN, "peligro": DANGER, "info": INFO, "dato": FG}
# Tonos limitados estrictamente a la misma familia oro / carbono / gris.
TILE_TONES = {
    "accent": ACCENT,
    "gold": ACCENT,
    "info": MUTED,
    "ok": ACCENT_LIGHT,
    "aviso": ACCENT,
    "peligro": DANGER,
    "dato": FG,
    "muted": MUTED,
}
_TILE_TONES_BASE = dict(TILE_TONES)

FONT_STACK = (
    '"SF Pro Text", "SF Pro Display", "Segoe UI Variable", "Segoe UI", '
    '"Inter", "Noto Sans", "DejaVu Sans", sans-serif'
)
_FONT_PREFERENCES = (
    "SF Pro Text",
    "SF Pro Display",
    "Segoe UI Variable",
    "Segoe UI",
    "Inter",
    "Noto Sans",
    "DejaVu Sans",
)


@lru_cache(maxsize=1)
def preferred_font_family() -> str:
    """Elige una sans moderna disponible; no descarga ni instala tipografías."""
    app = QApplication.instance()
    if app is None:  # pragma: no cover - QApplication todavía no inicializada
        return "Segoe UI"
    try:
        installed = {family.casefold(): family for family in QFontDatabase.families()}
    except TypeError:  # Compatibilidad con bindings Qt que exponen familias como método de instancia
        installed = {family.casefold(): family for family in QFontDatabase(app).families()}
    for requested in _FONT_PREFERENCES:
        if requested.casefold() in installed:
            return installed[requested.casefold()]
    return "Sans Serif"


@lru_cache(maxsize=32)
def _cached_stylesheet(assets_key: tuple[tuple[str, str], ...]) -> str:
    """Evita regenerar el QSS grande al volver a aplicar la paleta fija."""
    return _render_stylesheet(dict(assets_key))


def tint(color: str, alpha: float) -> str:
    """``rgba(...)`` a partir de un color de la paleta y una opacidad 0-1."""
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(channel * 2 for channel in color)
    red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha:g})"


# ------------------------------------------------------------------- iconos
_ASSET_CACHE: dict[str, str] = {}


def assets_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "QuickMechanic" / "assets"


def ensure_assets() -> dict[str, str]:
    """Dibuja (una sola vez) las flechas y el visto, y devuelve sus rutas."""
    if _ASSET_CACHE:
        return _ASSET_CACHE
    try:
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QPolygonF
    except Exception:  # pragma: no cover - sin Qt no hay interfaz que pintar
        return _ASSET_CACHE

    folder = assets_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover - carpeta de configuracion no escribible
        return _ASSET_CACHE

    def triangle(painter, direction: str, color: str, size: int) -> None:
        half = size / 2.0
        if direction == "up":
            points = [(half, half - 3.2), (half - 3.6, half + 2.6), (half + 3.6, half + 2.6)]
        elif direction == "down":
            points = [(half, half + 3.2), (half - 3.6, half - 2.6), (half + 3.6, half - 2.6)]
        else:  # right (desplegables)
            points = [(half + 3.2, half), (half - 2.6, half - 3.6), (half - 2.6, half + 3.6)]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(color)))
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))

    def check(painter, _direction: str, color: str, size: int) -> None:
        pen = QPen(QColor(color))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(
            QPolygonF([QPointF(size * 0.24, size * 0.52), QPointF(size * 0.43, size * 0.72),
                       QPointF(size * 0.78, size * 0.28)])
        )

    def save_icon(name: str, drawer, color: str, size: int = 16) -> None:
        """Dibuja el icono en PNG solo la primera vez y guarda su ruta."""
        path = folder / name
        if not path.is_file():
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            drawer(painter, "", color, size)
            painter.end()
            try:
                if not pixmap.save(str(path), "PNG"):
                    return
            except Exception:  # pragma: no cover - disco no escribible
                return
        _ASSET_CACHE[name] = path.as_posix()

    save_icon("arrow_up.png", lambda p, _d, color, size: triangle(p, "up", color, size), MUTED)
    save_icon("arrow_down.png", lambda p, _d, color, size: triangle(p, "down", color, size), MUTED)
    save_icon(
        "arrow_right.png", lambda p, _d, color, size: triangle(p, "right", color, size),
        ACCENT, 18,
    )
    save_icon("check.png", check, BG, 18)
    return _ASSET_CACHE


# ---------------------------------------------------------------------- QSS
_TEMPLATE = """    QWidget {{
    background: {bg};

    color: {fg};
    font-family: {font};
    font-size: 13px;
}}
QMainWindow, QDialog, QWizard {{ background: {bg}; }}
QToolTip {{
    background: {panel_alt};
    color: {fg};
    border: 1px solid {accent};
    border-left: 3px solid {accent};
    border-radius: 4px;
    padding: 5px 7px;
}}

/* ---------------------------------------------------------------- tarjetas */
QGroupBox {{
    background: {panel};
    border: 1px solid {border};
    border-left: 3px solid {accent};
    border-radius: 8px;
    margin-top: 16px;
    padding: 12px 12px 10px 12px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {accent};
    background: {bg};
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 11px;
}}

QFrame#statTile {{
    background: {panel_alt};
    border: 1px solid {border};
    border-top: 3px solid {accent};
    border-radius: 8px;
}}
QLabel#statValue {{
    background: transparent;
    color: {fg};
    font-size: 21px;
    font-weight: 800;
    letter-spacing: -0.5px;
}}
QLabel#statUnit {{
    background: transparent;
    color: {muted};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}}
QLabel#statTitle {{
    background: transparent;
    color: {muted};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}}
QLabel#pill {{
    border-radius: 9px;
    padding: 3px 9px;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

/* --------------------------------------------------------------- cabecera */
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {panel_alt}, stop:0.35 {panel}, stop:1 {bg});
    border: none;
    border-bottom: 3px solid {accent};
}}
QFrame#header QWidget {{ background: transparent; }}
QLabel#appTitle {{
    color: {fg};
    font-size: 21px;
    font-weight: 800;
    font-style: italic;
    letter-spacing: 3px;
}}
QLabel#appSubtitle {{
    color: {muted};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 3px;
}}
QLabel#appStripe {{
    background: {accent};
    border-radius: 2px;
}}
QLabel#headerNote {{ color: {muted}; font-size: 11px; }}

QFrame#carHeader {{
    background: {panel};
    border: 1px solid {border};
    border-left: 4px solid {accent};
    border-radius: 8px;
}}
QFrame#carHeader QWidget {{ background: transparent; }}
QLabel#carName {{ color: {fg}; font-size: 19px; font-weight: 800; }}
QLabel#carBrand {{ color: {muted}; font-size: 12px; }}

QFrame#footer {{ background: {panel}; border-top: 1px solid {border}; }}
QFrame#footer QWidget {{ background: transparent; }}
QLabel#footerStatus {{ color: {muted}; }}

/* ----------------------------------------------------------------- campos */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {panel_alt};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {accent};
    selection-color: {bg};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QComboBox:on {{
    border: 1px solid {accent};
    background: {panel};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {muted};
    background: {bg_alt};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 17px;
    margin: 1px 1px 0 0;
    border-left: 1px solid {border};
    border-top-right-radius: 5px;
    background: {panel};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 17px;
    margin: 0 1px 1px 0;
    border-left: 1px solid {border};
    border-bottom-right-radius: 5px;
    background: {panel};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {accent_dark}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{arrow_up}"); width: 9px; height: 9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{arrow_down}"); width: 9px; height: 9px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{ image: url("{arrow_right}"); width: 11px; height: 11px; }}
QComboBox QAbstractItemView {{
    background: {panel};
    border: 1px solid {accent};
    border-radius: 6px;
    selection-background-color: {accent};
    selection-color: {bg};
    outline: none;
}}

QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {border};
    border-radius: 4px;
    background: {panel_alt};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QCheckBox::indicator:checked {{ image: url("{check}"); }}
QCheckBox::indicator:disabled {{ background: {bg_alt}; border-color: {border}; }}

/* ----------------------------------------------------------------- botones */
QPushButton {{
    background: {raised};
    border: 1px solid {raised_border};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {raised_hover}; border-color: {accent}; }}
QPushButton:pressed {{ background: {panel}; }}
QPushButton:disabled {{ color: {muted}; background: {bg_alt}; border-color: {border}; }}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent}, stop:1 {accent_dark});
    color: #17140e;
    border: 1px solid {accent_light};
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent_light}, stop:1 {accent});
}}
QPushButton#primary:disabled {{ background: {panel_alt}; color: {muted}; border-color: {border}; }}
QPushButton#ghost {{
    background: transparent;
    border: 1px solid {border};
    color: {fg};
}}
QPushButton#ghost:hover {{ border-color: {accent}; color: {accent_light}; }}
QPushButton#danger:hover {{ border-color: {danger}; color: {danger}; }}
QPushButton#headerButton {{
    background: {raised};
    border: 1px solid {raised_border};
    color: {fg};
    padding: 5px 11px;
}}
QPushButton#headerButton:hover {{ border-color: {accent}; color: {accent_light}; }}
QPushButton#navButton {{
    background: transparent; border: 1px solid transparent; color: {muted};
    border-radius: 7px; padding: 11px 12px; text-align: left; font-weight: 700;
}}
QPushButton#navButton:hover {{ background: {panel_alt}; color: {fg}; }}
QPushButton#navButton:checked {{
    background: {gold_tint}; color: {accent_light}; border: 1px solid {accent_dark};
    border-left: 3px solid {accent};
}}
QFrame#navRail {{ background: {panel}; border: 1px solid {border}; border-radius: 10px; }}
QFrame#navRail QWidget {{ background: transparent; }}
QFrame#integrationCard {{ background: {panel}; border: 1px solid {border}; border-left: 3px solid {accent}; border-radius: 8px; }}
QFrame#integrationCard QWidget {{ background: transparent; }}
QFrame#guideStrip {{ background: {bg_alt}; border: 1px solid {border}; border-left: 3px solid {accent}; border-radius: 7px; }}
QFrame#guideStrip QWidget {{ background: transparent; }}
QFrame#communityNotification {{ background: {gold_tint}; border: 1px solid {accent_dark}; border-left: 3px solid {accent}; border-radius: 0; }}
QFrame#communityNotification QWidget {{ background: transparent; }}
QLabel#communityBadge {{ color: {accent_light}; font-size: 10px; font-weight: 900; letter-spacing: 1px; }}
QLabel#communityMessage {{ color: {fg}; font-size: 12px; }}
QLabel#guideStripText {{ color: {muted}; font-size: 11px; font-weight: 600; }}
QFrame#footer {{ background: {panel}; border-top: 1px solid {border}; }}
QLabel#integrationMark {{ color: {accent}; background: {bg}; border: 1px solid {accent_dark}; border-radius: 8px; font-weight: 900; }}
QLabel#integrationTitle {{ color: {fg}; font-size: 10px; font-weight: 900; letter-spacing: 1.5px; }}
QLabel#integrationStatus {{ font-size: 10px; }}
QLabel#integrationPath {{ color: {muted}; font-size: 10px; }}
QFrame#guideCard {{ background: {bg_alt}; border: 1px solid {border}; border-left: 3px solid {accent}; border-radius: 12px; }}
QLabel#guideEyebrow {{ color: {accent}; font-weight: 800; font-size: 10px; letter-spacing: 2px; }}
QLabel#guideTitle {{ color: {fg}; font-size: 23px; font-weight: 800; }}
QLabel#guideSubtitle {{ color: {muted}; font-size: 12px; }}
QLabel#guideStep {{ color: {accent_light}; font-size: 12px; font-weight: 900; letter-spacing: 1.5px; }}
QLabel#guideBody {{ color: {fg}; font-size: 15px; line-height: 1.4; }}
QLabel#guideProgress {{ color: {muted}; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }}
QPushButton#sectionChip {{ background: {bg_alt}; color: {muted}; border: 1px solid {border}; border-radius: 14px; padding: 5px 10px; font-size: 10px; font-weight: 800; }}
QLabel#pageEyebrow {{ color: {accent}; font-size: 10px; font-weight: 900; letter-spacing: 2px; }}
QLabel#pageTitle {{ color: {fg}; font-size: 23px; font-weight: 800; }}
QLabel#pageDescription {{ color: {muted}; font-size: 11px; }}
QLabel#heroTitle {{ color: {fg}; font-size: 26px; font-weight: 900; font-style: italic; }}
QLabel#heroSubtitle {{ color: {muted}; font-size: 12px; }}
QLabel#sectionLabel {{ color: {accent}; font-size: 10px; font-weight: 900; letter-spacing: 1.5px; }}
QPushButton#heroButton {{ background: {gold_tint}; color: {accent_light}; border: 1px solid {accent_dark}; border-radius: 7px; padding: 7px 12px; font-weight: 800; }}
QPushButton#heroButton:hover {{ background: {accent_dark}; color: {fg}; }}
QCheckBox#guideStartup {{ color: {muted}; font-size: 11px; spacing: 7px; }}
QPushButton#navButton {{ min-height: 40px; padding-left: 14px; }}
QFrame#workspaceCard {{ background: {bg_alt}; border: 1px solid {border}; border-radius: 10px; }}
QWidget#pageHeading {{ background: transparent; }}
QSlider#zoomSlider::groove:horizontal {{ height: 8px; background: {panel_alt}; border: 1px solid {border}; border-radius: 4px; }}
QSlider#zoomSlider::sub-page:horizontal {{ background: {accent}; border-radius: 4px; }}
QSlider#zoomSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -6px 0; border-radius: 10px; background: {accent_light}; border: 2px solid {accent}; }}
QSlider#zoomSlider::handle:horizontal:hover {{ background: #f2dfa6; }}
QPushButton#saveButton {{ min-width: 142px; min-height: 36px; }}

/* ------------------------------------------------------------------ listas */
QListWidget {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 8px;
    outline: none;
    padding: 4px;
}}
QListWidget::item {{
    padding: 7px 8px;
    border-radius: 5px;
    border-left: 3px solid transparent;
    color: {fg};
}}
QListWidget::item:hover {{ background: {panel_alt}; }}
QListWidget::item:selected {{
    background: {list_selected};
    border-left: 3px solid {accent};
    color: #ffffff;
    font-weight: 600;
}}
QListWidget::item:selected:!active {{ background: {list_selected}; color: #ffffff; }}

/* --------------------------------------------------------------------- tabs */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 8px;
    top: -1px;
    background: {bg};
}}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 8px 18px 7px 18px;
    margin-right: 4px;
    color: {muted};
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    font-size: 11px;
}}
QTabBar::tab:hover {{ color: {fg}; border-bottom-color: {border}; }}
QTabBar::tab:selected {{ color: {accent}; border-bottom-color: {accent}; }}
QTabBar::tab:disabled {{ color: #5b6472; }}

/* ------------------------------------------------------------ varios / misc */
QSplitter::handle {{ background: transparent; width: 8px; }}
QSplitter::handle:hover {{ background: {tint_accent}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {raised_border}; border-radius: 5px; min-height: 34px; }}
QScrollBar::handle:vertical:hover {{ background: {accent}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {raised_border}; border-radius: 5px; min-width: 34px; }}
QScrollBar::handle:horizontal:hover {{ background: {accent}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTextBrowser {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 10px 14px;
}}
QProgressBar {{
    background: {panel_alt};
    border: 1px solid {border};
    border-radius: 6px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 5px; }}

QSlider::groove:horizontal {{
    height: 6px;
    background: {panel_alt};
    border: 1px solid {border};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 14px;
    margin: -6px 0;
    border-radius: 8px;
    background: {fg};
    border: 2px solid {accent};
}}
QSlider::handle:horizontal:hover {{ background: {accent_light}; }}

QLabel#banner {{
    background: {warn_tint};
    color: {warn};
    border: 1px solid {warn};
    border-left: 4px solid {warn};
    border-radius: 8px;
    padding: 9px 12px;
}}
QLabel#previewArea {{
    background: {bg_alt};
    border: 1px solid {border};
    border-radius: 8px;
    color: {muted};
}}
QFrame#previewCard {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 8px;
}}
QFrame#dashboardChart {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 8px;
}}
QLabel#dashboardHeading {{
    color: {accent};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.5px;
}}
QListWidget::item {{ min-height: 30px; }}
QPushButton#iconButton {{ padding: 5px 9px; font-size: 16px; font-weight: 800; }}
QFrame#header {{ border-top: 2px solid {accent_light}; }}
QFrame#previewCard QWidget {{ background: transparent; }}
QLabel#previewTitle {{ color: {fg}; font-weight: 800; font-size: 14px; }}
QLabel#previewSubtitle {{ color: {muted}; font-size: 11px; }}
QLabel#previewBadge {{ background: transparent; }}
QLabel#sectionRule {{ background: {border}; }}
"""


def stylesheet(assets: dict[str, str] | None = None) -> str:
    """Hoja de estilo completa; ``assets`` da las rutas de las flechas."""
    assets = assets if assets else {}
    key = tuple(sorted((str(name), str(path)) for name, path in assets.items()))
    return _cached_stylesheet(key)


def _render_stylesheet(assets: dict[str, str]) -> str:
    return _TEMPLATE.format(
        bg=BG,
        bg_alt=BG_ALT,
        panel=PANEL,
        panel_alt=PANEL_ALT,
        raised=RAISED,
        raised_border=RAISED_BORDER,
        raised_hover=RAISED_HOVER,
        border=BORDER,
        fg=FG,
        muted=MUTED,
        accent=ACCENT,
        accent_light=ACCENT_LIGHT,
        accent_dark=ACCENT_DARK,
        danger=DANGER,
        warn=WARN,
        font=FONT_STACK,
        arrow_up=assets.get("arrow_up.png", ""),
        arrow_down=assets.get("arrow_down.png", ""),
        arrow_right=assets.get("arrow_right.png", ""),
        check=assets.get("check.png", ""),
        tint_bg=tint("#ffffff", 0.04),
        tint_accent=tint(ACCENT, 0.25),
        list_selected=tint(ACCENT, 0.18),
        warn_tint=tint(WARN, 0.12),
        gold_tint=tint(ACCENT, 0.12),
    )


# Compatibilidad: hoja de estilo sin iconos (sin QApplication no se pueden pintar)
QSS = stylesheet()


def apply(app) -> None:
    """Aplica el tema a la QApplication (colores, fuente y hoja de estilo)."""
    from PyQt6.QtGui import QColor, QFont, QPalette

    # Acento intencionadamente fijo: los ajustes antiguos no pueden cambiar la marca.
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(FG))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.Text, QColor(FG))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(FG))
    palette.setColor(QPalette.ColorRole.Light, QColor(RAISED_HOVER))
    palette.setColor(QPalette.ColorRole.Mid, QColor(BORDER))
    palette.setColor(QPalette.ColorRole.Dark, QColor(BG_ALT))
    palette.setColor(QPalette.ColorRole.Shadow, QColor(BG))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(FG))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(palette)

    font = QFont(preferred_font_family())
    font.setPointSize(9)
    app.setFont(font)

    TILE_TONES.clear()
    TILE_TONES.update(_TILE_TONES_BASE)
    app.setStyleSheet(stylesheet(ensure_assets()))
