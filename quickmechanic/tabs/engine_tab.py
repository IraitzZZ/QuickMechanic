"""Pestaña Motor: limitador, turbo y editor tabular de power.lut."""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..qt_i18n import QCheckBox, QFrame, QLabel, QMessageBox, QPushButton, QScrollArea, QSlider, QWidget

from .. import theme, units, widgets
from ..car_data import CarData

_TURBO_ROWS = (
    ("MAX_BOOST", "Boost maximo", 0.05, 2),
    ("WASTEGATE", "Wastegate", 0.05, 2),
    ("DISPLAY_MAX_BOOST", "Boost del display", 0.05, 2),
    ("REFERENCE_RPM", "Rpm de referencia", 200, 0),
    ("LAG_UP", "Lag al subir", 0.001, 3),
    ("LAG_DN", "Lag al bajar", 0.001, 3),
    ("GAMMA", "Gamma", 0.1, 2),
)


class MotorTab(QWidget):
    """Editor de engine.ini + power.lut."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.car: CarData | None = None
        self._loading = False
        self._turbo_fields: dict[str, QWidget] = {}
        self.turbo_warning: QLabel | None = None
        self.turbo_estimate: QLabel | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self.stats = widgets.StatRow()
        self.stats.add("torque", "Par maximo", "Nm", "accent", "Pico de la curva de par")
        self.stats.add("power", "Potencia", "CV", "ok", "Potencia maxima de la curva")
        self.stats.add("ratio", "Peso/potencia", "CV/t", "info", "Potencia por tonelada")
        self.stats.add("cut", "Corte", "rpm", "aviso", "LIMITER: vueltas a las que corta")
        outer.addWidget(self.stats, 0)

        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        outer.addWidget(body, 1)

        # ---------------------------------------------------------- izquierda
        column = QWidget()
        column.setMaximumWidth(420)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(8)

        engine_panel = widgets.Panel("Motor")
        self.limiter = widgets.ispin(
            1000, 20000, 100, "", "LIMITER: revoluciones a las que corta la inyeccion"
        )
        self.idle = widgets.ispin(300, 5000, 50, "", "MINIMUM: regimen de ralenti")
        self.inertia = widgets.dspin(
            0.01, 2.0, 0.005, 3, "", "INERTIA: menos inercia = el motor sube de vueltas antes"
        )
        engine_panel.add("Limitador", self.limiter, "rpm")
        engine_panel.add("Ralenti", self.idle, "rpm")
        engine_panel.add("Inercia del motor", self.inertia, "")
        column_layout.addWidget(engine_panel)

        self.curve_panel = widgets.Panel("Curva de potencia")
        self.scale = widgets.dspin(
            0.2,
            3.0,
            0.01,
            2,
            "",
            "Multiplica la curva de par entera antes de guardar power.lut",
        )
        self.scale.setValue(1.0)
        self.curve_panel.add("Multiplicador de par", self.scale, "x")
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(20, 300)
        self.scale_slider.setSingleStep(5)
        self.scale_slider.setPageStep(10)
        self.scale_slider.setValue(100)
        self.scale_slider.setToolTip(
            "Arrastra para reescalar la curva entera: 100 = curva original (x1.00)"
        )
        self.curve_panel.add_widget(self.scale_slider)
        buttons = QWidget()
        button_layout = QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.reset_curve = QPushButton("Curva original")
        self.reset_curve.setToolTip("Deja el multiplicador en 1.0 sin tocar el fichero")
        button_layout.addWidget(self.reset_curve)
        self.curve_panel.add_widget(buttons)
        self.peak_label = self.curve_panel.add_note("", "dato")
        self.power_weight_label = self.curve_panel.add_note("", "dato")
        self.curve_info = self.curve_panel.add_note("", "info")
        column_layout.addWidget(self.curve_panel)

        turbo_holder = QWidget()
        self.turbo_slot = QVBoxLayout(turbo_holder)
        self.turbo_slot.setContentsMargins(0, 0, 0, 0)
        column_layout.addWidget(turbo_holder)
        column_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(column)
        root.addWidget(scroll, 0)

        # ------------------------------------------------------------- tabla de curva editable
        right = widgets.Panel("Curva power.lut · editor avanzado de puntos")
        right.add_note(
            "Los valores se leen directamente de power.lut. Editar el par de un punto cambia "
            "solo ese valor; no hay interpolación ni mediciones de pista.", "info"
        )
        self.curve_table = QTableWidget(0, 3)
        self.curve_table.setHorizontalHeaderLabels(["RPM", "Par (Nm)", "Potencia calculada (CV)"])
        self.curve_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.curve_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.curve_table.horizontalHeader().setStretchLastSection(True)
        self.curve_table.horizontalHeader().setSectionResizeMode(0, self.curve_table.horizontalHeader().ResizeMode.ResizeToContents)
        self.curve_table.horizontalHeader().setSectionResizeMode(1, self.curve_table.horizontalHeader().ResizeMode.ResizeToContents)
        self.curve_table.verticalHeader().setVisible(False)
        right.add_widget(self.curve_table)
        root.addWidget(right, 1)
        self.curve_table.itemChanged.connect(self._on_curve_cell_changed)
        self._clear_curve_table()

        self.limiter.valueChanged.connect(self._store_engine)
        self.idle.valueChanged.connect(self._store_engine)
        self.inertia.valueChanged.connect(self._store_engine)
        self.scale.valueChanged.connect(self._on_scale)
        self.scale_slider.valueChanged.connect(self._on_slider)
        self.reset_curve.clicked.connect(lambda: self.scale.setValue(1.0))

    # ------------------------------------------------------------ edición local
    def _clear_curve_table(self) -> None:
        self.curve_table.blockSignals(True)
        self.curve_table.setRowCount(0)
        self.curve_table.blockSignals(False)

    def _on_curve_cell_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or self.car is None or item.column() != 1:
            return
        try:
            torque = float(item.text().replace(",", "."))
        except ValueError:
            return
        if not math.isfinite(torque) or torque < 0 or torque > 20000:
            self._refresh_curve()
            return
        if self.car.set_power_point(item.row(), torque):
            self._refresh_curve()
            self._refresh_summary()
            self.changed.emit()

    # ------------------------------------------------------------------ carga
    def load(self, car: CarData | None) -> None:
        self.car = car
        self._loading = True
        try:
            available = bool(car is not None and car.editable)
            self.setEnabled(available)
            if not available:
                self._clear_curve_table()
                self.stats.clear_values()
                self.peak_label.setText("")
                self.power_weight_label.setText("")
                self.curve_info.setText("")
                widgets.clear_layout(self.turbo_slot)
                return
            self.limiter.setValue(car.limiter)
            self.idle.setValue(car.idle_rpm)
            self.inertia.setValue(car.engine_inertia)
            current_scale = car.power_scale if car.power_scale_applied else 1.0
            self.scale.setValue(current_scale)
            self.scale_slider.setValue(int(round(current_scale * 100)))
            self._build_turbo_panel()
            self._refresh_curve()
            self._refresh_summary()
        finally:
            self._loading = False

    # ------------------------------------------------------------------ guardar
    def _store_engine(self) -> None:
        if self._loading or self.car is None:
            return
        self.car.limiter = self.limiter.value()
        self.car.idle_rpm = self.idle.value()
        self.car.engine_inertia = self.inertia.value()
        self._refresh_summary()
        self.changed.emit()

    def _on_scale(self) -> None:
        if self._loading or self.car is None:
            return
        self.scale_slider.blockSignals(True)
        self.scale_slider.setValue(int(round(self.scale.value() * 100.0)))
        self.scale_slider.blockSignals(False)
        self.car.set_power_scale(self.scale.value())
        self._refresh_curve()
        self._refresh_summary()
        self.changed.emit()

    def _on_slider(self, value: int) -> None:
        """El deslizador manda sobre el campo numerico, pero se avisa una sola vez."""
        if self._loading or self.car is None:
            return
        self.scale.blockSignals(True)
        self.scale.setValue(value / 100.0)
        self.scale.blockSignals(False)
        self._on_scale()

    def _store_turbo(self) -> None:
        if self._loading or self.car is None:
            return
        payload: dict[str, float] = {}
        for key, widget in self._turbo_fields.items():
            if isinstance(widget, QCheckBox):
                payload[key] = 1.0 if widget.isChecked() else 0.0
            else:
                payload[key] = float(widget.value())
        self.car.set_turbo(0, **payload)
        self._refresh_turbo_notes()
        self._refresh_summary()
        self.changed.emit()

    # ------------------------------------------------------------------- turbo
    def _build_turbo_panel(self) -> None:
        widgets.clear_layout(self.turbo_slot)
        self._turbo_fields.clear()
        self.turbo_warning = None
        self.turbo_estimate = None
        if self.car is None:
            return

        turbos = self.car.turbos()
        if not turbos:
            panel = widgets.Panel("Turbo")
            panel.add_note("Coche atmosferico: engine.ini no tiene ninguna seccion [TURBO_n].", "info")
            add = QPushButton("Anadir turbo ([TURBO_0] con valores de Kunos)")
            add.clicked.connect(self._add_turbo)
            panel.add_widget(add)
            panel.add_note(
                "El turbo no cambia el .lut: multiplica el par en tiempo real "
                "por (1 + MAX_BOOST) cuando esta lleno.",
                "info",
            )
            self.turbo_slot.addWidget(panel)
            return

        turbo = turbos[0]
        panel = widgets.Panel(f"Turbo ({turbo.section})")
        for key, label, step, decimals in _TURBO_ROWS:
            value = float(getattr_lower(turbo, key))
            decimal_field = decimals > 0
            if decimal_field:
                field = widgets.dspin(0.0, 5.0, step, decimals, "", _TURBO_TIPS.get(key, ""))
            else:
                field = widgets.ispin(0, 20000, int(step), "", _TURBO_TIPS.get(key, ""))
            field.blockSignals(True)
            field.setValue(value if decimal_field else int(round(value)))
            field.blockSignals(False)
            field.valueChanged.connect(self._store_turbo)
            self._turbo_fields[key] = field
            panel.add(label, field)

        cockpit = QCheckBox("Ajustable desde el cockpit")
        cockpit.setToolTip("COCKPIT_ADJUSTABLE: permite mover el boost con un mando en pista")
        cockpit.setChecked(turbo.cockpit_adjustable)
        cockpit.toggled.connect(self._store_turbo)
        self._turbo_fields["COCKPIT_ADJUSTABLE"] = cockpit
        panel.add_widget(cockpit)

        self.turbo_warning = panel.add_note("", "aviso")
        self.turbo_estimate = panel.add_note("", "dato")

        remove = QPushButton("Quitar turbo (comenta la seccion)")
        remove.clicked.connect(self._remove_turbo)
        panel.add_widget(remove)

        self.turbo_slot.addWidget(panel)
        self._refresh_turbo_notes()

    def _refresh_turbo_notes(self) -> None:
        if self.car is None or self.turbo_warning is None:
            return
        turbos = self.car.turbos()
        if not turbos:
            return
        turbo = turbos[0]
        self.turbo_warning.setText("")
        self.turbo_warning.setStyleSheet("")
        threshold = self.car.damage["turbo_threshold"]
        if threshold and turbo.max_boost > threshold:
            self.turbo_warning.setText(
                f"Atencion: MAX_BOOST {turbo.max_boost:.2f} supera el umbral de dano del motor "
                f"({threshold:.2f}). El turbo se rompera en pista."
            )
            self.turbo_warning.setStyleSheet(f"color: {theme.DANGER};")

        if self.turbo_estimate is not None:
            rpm, torque = self.car.peak_torque()
            boosted = torque * (1.0 + turbo.max_boost)
            hp = units.hp_from_torque(boosted, rpm)
            self.turbo_estimate.setText(
                f"Con el turbo lleno: ~{boosted:.0f} Nm y ~{hp:.0f} CV a {rpm:.0f} rpm "
                f"(la curva de abajo es la del motor sin boost)."
            )

    def _add_turbo(self) -> None:
        if self.car is None:
            return
        answer = QMessageBox.question(
            self,
            "Anadir turbo",
            "Se va a anadir una seccion [TURBO_0] a engine.ini con los valores de Kunos\n"
            "(MAX_BOOST 1.0 = par x2 con el turbo lleno).\n\n"
            "Se puede deshacer: el .bak guarda el engine.ini original.\n\nContinuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.car.add_turbo()
        self._build_turbo_panel()
        self._refresh_summary()
        self.changed.emit()

    def _remove_turbo(self) -> None:
        if self.car is None:
            return
        answer = QMessageBox.question(
            self,
            "Quitar turbo",
            "Se van a comentar las claves de [TURBO_0] (el coche pasa a ser atmosferico).\n\n"
            "Continuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.car.remove_turbo()
        self._build_turbo_panel()
        self._refresh_summary()
        self.changed.emit()

    # ------------------------------------------------------------- curva tabular
    def _refresh_curve(self) -> None:
        if self.car is None or not self.car.editable:
            self._clear_curve_table()
            return
        lut = self.car.power_lut
        points = self.car.power_points()
        if lut is None or not points:
            self._clear_curve_table()
            self.curve_info.setText(
                f"No se ha encontrado {self.car.power_curve_file} en la carpeta data del coche."
            )
            return

        xs = [point[0] for point in points]
        self.curve_table.blockSignals(True)
        self.curve_table.setRowCount(len(points))
        for row, (rpm, torque_nm) in enumerate(points):
            values = (f"{rpm:g}", f"{torque_nm:.3f}".rstrip("0").rstrip("."),
                      f"{units.hp_from_torque(torque_nm, rpm):.2f}")
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                if column != 1:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.curve_table.setItem(row, column, cell)
        self.curve_table.blockSignals(False)

        scale_text = ""
        if abs(self.car.power_scale - 1.0) > 1e-9:
            scale_text = f"  ·  curva escalada x{self.car.power_scale:.2f}"
        self.curve_info.setText(
            f"{self.car.power_curve_file}: {lut.n_rows} puntos, "
            f"{xs[0]:.0f}-{xs[-1]:.0f} rpm{scale_text}"
        )

    def _refresh_summary(self) -> None:
        if self.car is None:
            return
        rpm_t, torque = self.car.peak_torque()
        rpm_hp, hp = self.car.peak_power()
        self.peak_label.setText(
            f"Par maximo {torque:.0f} Nm a {rpm_t:.0f} rpm  ·  potencia {hp:.0f} CV a {rpm_hp:.0f} rpm"
        )
        cv_per_tonne, kg_per_cv = self.car.power_weight()
        self.power_weight_label.setText(
            f"{cv_per_tonne:.0f} CV por tonelada  ·  {kg_per_cv:.2f} kg/CV "
            f"({self.car.mass:.0f} kg)"
        )
        self.curve_info.setStyleSheet(f"color: {theme.MUTED};")
        self.stats.set("torque", f"{torque:.0f}")
        self.stats.set("power", f"{hp:.0f}")
        self.stats.set("ratio", f"{cv_per_tonne:.0f}")
        self.stats.set("cut", f"{self.car.limiter}")


_TURBO_TIPS = {
    "MAX_BOOST": "MAX_BOOST: multiplicador de par con el turbo lleno (2.0 = par x3)",
    "WASTEGATE": "WASTEGATE: nivel maximo antes de que la wastegate corte el boost",
    "DISPLAY_MAX_BOOST": "Valor que muestran los displays del cockpit",
    "REFERENCE_RPM": "Rpm a las que el turbo alcanza el boost maximo a fondo",
    "LAG_UP": "LAG_UP: 0.99 sube lento, 0.999 sube casi instantaneo",
    "LAG_DN": "LAG_DN: lo mismo al soltar el gas",
    "GAMMA": "GAMMA: forma de la curva de subida del turbo",
}


def getattr_lower(turbo, key: str):
    """MAX_BOOST -> turbo.max_boost."""
    return getattr(turbo, key.lower(), 0)
