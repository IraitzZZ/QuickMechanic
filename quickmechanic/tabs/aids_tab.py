"""Pestana para asistencias ABS/TC declaradas por el propio coche."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from .. import theme, widgets
from ..car_data import CarData


class AidsTab(QWidget):
    """Editor conservador: no añade ayudas que el coche no soporte."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.car: CarData | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.overview = widgets.StatRow()
        self.overview.add("abs", "ABS", "", "gold")
        self.overview.add("tc", "Control traccion", "", "info")
        self.overview.add("file", "Electronics.ini", "", "ok")
        layout.addWidget(self.overview)

        intro = widgets.Panel("Asistencias del vehiculo")
        intro.add_note(
            "Quick Mechanic solo cambia PRESENT y ACTIVE si ya existen en electronics.ini. "
            "No crea soporte de hardware ni modifica data.acd. Guarda los cambios para aplicarlos "
            "al coche en Assetto Corsa.",
            "info",
        )
        layout.addWidget(intro)

        self.abs_panel = widgets.Panel("ABS · antibloqueo de frenos")
        self.abs_present = QCheckBox("Este coche lleva ABS")
        self.abs_active = QCheckBox("ABS activo en pista")
        self.abs_panel.add_widget(self.abs_present)
        self.abs_panel.add_widget(self.abs_active)
        self.abs_note = self.abs_panel.add_note("", "info")
        layout.addWidget(self.abs_panel)

        self.tc_panel = widgets.Panel("TC · control de traccion")
        self.tc_present = QCheckBox("Este coche lleva control de traccion")
        self.tc_active = QCheckBox("Control de traccion activo en pista")
        self.tc_panel.add_widget(self.tc_present)
        self.tc_panel.add_widget(self.tc_active)
        self.tc_note = self.tc_panel.add_note("", "info")
        layout.addWidget(self.tc_panel)

        self.compatibility = QLabel("")
        self.compatibility.setWordWrap(True)
        self.compatibility.setStyleSheet(f"color:{theme.MUTED};")
        layout.addWidget(self.compatibility)
        layout.addStretch(1)

        self.abs_present.toggled.connect(lambda value: self._store("ABS", present=value))
        self.abs_active.toggled.connect(lambda value: self._store("ABS", active=value))
        self.tc_present.toggled.connect(lambda value: self._store("TC", present=value))
        self.tc_active.toggled.connect(lambda value: self._store("TC", active=value))
        self.load(None)

    def load(self, car: CarData | None) -> None:
        self.car = car
        self._loading = True
        try:
            available = bool(car and car.editable)
            self.setEnabled(available)
            states = car.driver_aids() if available else {}
            exists = bool(car and car.has_file("electronics.ini"))
            self.overview.set("file", "Detectado" if exists else "No disponible")
            self._load_aid("ABS", states.get("ABS"), self.abs_present, self.abs_active, self.abs_note)
            self._load_aid("TC", states.get("TC"), self.tc_present, self.tc_active, self.tc_note)
            if not available:
                message = "Selecciona un coche con data/ extraida para inspeccionar las asistencias."
            elif not exists:
                message = "Este coche no incluye electronics.ini abierto. No se han inventado parámetros; " \
                          "si sus datos están en data.acd, extráelos con Content Manager y vuelve a sincronizar."
            elif not states:
                message = "electronics.ini está presente, pero no declara secciones ABS/TC compatibles " \
                          "con los interruptores PRESENT/ACTIVE. Se mantiene intacto."
            else:
                message = "Los estados se leen de electronics.ini. El comportamiento final depende " \
                          "del modelo de coche y de las opciones que Assetto Corsa permita en pista."
            self.compatibility.setText(message)
        finally:
            self._loading = False

    def _load_aid(self, key: str, state, present: QCheckBox, active: QCheckBox, note: QLabel) -> None:
        supported = bool(state and state.get("available"))
        self.overview.set("abs" if key == "ABS" else "tc", "Compatible" if supported else "No declarado")
        present.setEnabled(supported)
        active.setEnabled(supported and bool(state.get("present")))
        present.setChecked(bool(state and state.get("present")))
        active.setChecked(bool(state and state.get("active")))
        note.setText(
            f"Seccion [{state['section']}] encontrada. Se modifican solo las claves que ya existen."
            if supported else "El coche no declara una seccion compatible; no se puede activar desde aquí."
        )

    def _store(self, aid: str, *, present: bool | None = None, active: bool | None = None) -> None:
        if self._loading or self.car is None:
            return
        if not self.car.set_driver_aid(aid, present=present, active=active):
            self.load(self.car)
            return
        state = self.car.driver_aids().get(aid)
        checkbox = self.abs_active if aid == "ABS" else self.tc_active
        checkbox.setEnabled(bool(state and state.get("present")))
        self.changed.emit()
