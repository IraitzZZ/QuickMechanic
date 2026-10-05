"""Pestana Diagnostico: ficha del coche, avisos y estado de los ficheros.

Es la pestana que se abre sola cuando el coche no se puede editar (solo trae
``data.acd``), asi que explica los dos caminos para desbloquearlo y resume todo
lo que Quick Mechanic ha leido del coche.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout
from ..qt_i18n import QWidget

from .. import skins, theme
from ..car_data import CarData

_TONE_COLOR = {
    "peligro": theme.DANGER,
    "aviso": theme.WARN,
    "info": theme.INFO,
    "ok": theme.OK,
}

_FILES = (
    "engine.ini",
    "drivetrain.ini",
    "suspensions.ini",
    "brakes.ini",
    "car.ini",
    "tyres.ini",
    "setup.ini",
)


def _esc(text: str) -> str:
    """Escapa el texto que viene del coche (ui_car.json puede traer cualquier cosa)."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class InfoTab(QWidget):
    """Resumen y diagnostico del coche seleccionado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        layout.addWidget(self.view)

    def load(
        self,
        car: CarData | None,
        status: str = "",
        meta: skins.CarMeta | None = None,
    ) -> None:
        self.view.setHtml(self._html(car, status, meta))

    # ------------------------------------------------------------------ vistas
    def _html(
        self, car: CarData | None, status: str, meta: skins.CarMeta | None
    ) -> str:
        if car is None or not car.editable:
            return self._wrap(self._locked_html(meta, status))
        return self._wrap(self._editable_html(car, status, meta))

    def _locked_html(self, meta: skins.CarMeta | None, status: str) -> str:
        title = _esc(meta.title) if meta and meta.title else "Coche sin datos editables"
        steps = (
            "<ol>"
            "<li>Abre Content Manager.</li>"
            "<li>Boton derecho sobre el coche → <b>Data</b> → <b>Unpack</b> "
            "(o el boton de extraer data.acd de tu herramienta habitual).</li>"
            "<li>Vuelve aqui y pulsa <b>Recargar lista</b>.</li>"
            "</ol>"
        )
        return (
            f"<h2 style='color:{theme.ACCENT};margin-bottom:2px'>{title}</h2>"
            f"{self._specs_table(meta)}"
            "<h3>Este coche no se puede editar todavia</h3>"
            "<p>AC guarda la fisica de muchos coches dentro de <b>data.acd</b>, un archivo "
            "comprimido propio del juego. Quick Mechanic trabaja sobre la carpeta "
            "<b>data/</b> con los .ini abiertos.</p>"
            f"<p>Para poder editarlo:</p>{steps}"
            "<p>Tambien puedes usar <b>Abrir carpeta data...</b> y elegir la carpeta ya "
            "extraida donde la tengas.</p>"
            + self._description(meta)
            + self._source_note(status)
        )

    def _editable_html(
        self, car: CarData, status: str, meta: skins.CarMeta | None
    ) -> str:
        alerts = "".join(
            f"<li><b style='color:{_TONE_COLOR.get(level, theme.FG)}'>"
            f"{level.upper()}</b> · {_esc(text)}</li>"
            for level, text in car.alerts()
        )
        rows = "".join(
            f"<tr><td style='color:{theme.MUTED};padding:2px 16px 2px 0'>{_esc(label)}</td>"
            f"<td><b>{_esc(value)}</b></td></tr>"
            for label, value in car.summary()
        )
        files = "".join(
            self._file_row(car, name)
            for name in _FILES + (car.power_curve_file, "coast.lut", "ratios.rto", "final.rto")
        )
        return (
            f"<h2 style='color:{theme.ACCENT};margin-bottom:2px'>{_esc(car.ui_name)}</h2>"
            f"{self._specs_table(meta)}"
            "<h3>Avisos</h3>"
            f"<ul style='margin-top:2px'>{alerts}</ul>"
            "<h3>Ficha tecnica (leida de los .ini)</h3>"
            f"<table cellspacing='0'>{rows}</table>"
            "<h3>Ficheros de fisica</h3>"
            f"<table cellspacing='0'>{files}</table>"
            + self._description(meta)
            + "<h3>Como guarda Quick Mechanic</h3>"
            "<p>Al guardar se reescriben <b>solo las lineas que cambian</b>: los comentarios y "
            "el orden original del .ini se mantienen tal cual. La primera vez que se toca un "
            "fichero se crea una copia ZIP completa y un <b>.bak</b> original, que no se sobrescribe "
            "despues.</p>"
            + self._source_note(status)
        )

    @staticmethod
    def _file_row(car: CarData, name: str) -> str:
        if car.has_file(name):
            value = f"<span style='color:{theme.OK}'>si</span>"
        else:
            value = f"<span style='color:{theme.WARN}'>falta</span>"
        return (
            f"<tr><td style='color:{theme.MUTED};padding:2px 16px 2px 0'>{_esc(name)}</td>"
            f"<td>{value}</td></tr>"
        )

    @staticmethod
    def _specs_table(meta: skins.CarMeta | None) -> str:
        if meta is None or not meta.specs:
            return ""
        cells = "".join(
            f"<tr><td style='color:{theme.MUTED};padding:2px 16px 2px 0'>{_esc(label)}</td>"
            f"<td><b>{_esc(value)}</b></td></tr>"
            for label, value in meta.specs
        )
        tags = ""
        if meta.tags:
            tags = (
                f"<p style='color:{theme.MUTED};margin-top:2px'>"
                " · ".join(_esc(tag) for tag in meta.tags) + "</p>"
            )
        return (
            f"<h3>Ficha del mod (ui_car.json)</h3>"
            f"<table cellspacing='0'>{cells}</table>{tags}"
        )

    @staticmethod
    def _description(meta: skins.CarMeta | None) -> str:
        if meta is None or not meta.description:
            return ""
        text = _esc(meta.description).replace("\n\n", "</p><p>").replace("\n", "<br>")
        return f"<h3>Descripcion del mod</h3><p>{text}</p>"

    @staticmethod
    def _source_note(status: str) -> str:
        if not status:
            return ""
        return f"<p style='color:{theme.MUTED}'>Origen: {_esc(status)}</p>"

    @staticmethod
    def _wrap(body: str) -> str:
        return (
            "<html><head><style>"
            f"body {{ color: {theme.FG}; font-size: 13px; }}"
            f"h2 {{ margin: 0 0 8px 0; }}"
            f"h3 {{ color: {theme.ACCENT}; font-size: 12px; letter-spacing: 1px;"
            " text-transform: uppercase; margin: 14px 0 4px 0; }"
            f"a {{ color: {theme.INFO}; }}"
            "</style></head>"
            f"<body>{body}</body></html>"
        )
