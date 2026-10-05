"""Pestana Chasis: suspension, barras estabilizadoras, frenos y peso.

AC guarda la suspension en unidades del sistema internacional (N/m, N·s/m) pero
en el garaje se piensa en N/mm y N·s/mm, que es lo que se ve aqui. Los rangos
minimos y maximos se toman de setup.ini cuando el coche los declara, para no
salirse de lo que AC acepta en el setup.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
)

from ..qt_i18n import QFrame, QScrollArea, QWidget

from .. import theme, units, widgets
from ..car_data import CarData


class ChassisTab(QWidget):
    """Editor de suspensions.ini, brakes.ini y car.ini."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.car: CarData | None = None
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self.stats = widgets.StatRow()
        self.stats.add("mass", "Peso", "kg", "accent", "TOTALMASS de car.ini")
        self.stats.add("ratio", "Peso/potencia", "CV/t", "ok")
        self.stats.add(
            "front_hz", "Frec. delantera", "Hz", "info",
            "Frecuencia natural del eje delantero (1.2 Hz calle, 2.5-4 GT)",
        )
        self.stats.add("rear_hz", "Frec. trasera", "Hz", "info")
        outer.addWidget(self.stats, 0)

        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        outer.addWidget(body, 1)

        # ---------------------------------------------------------- izquierda
        column = QWidget()
        column.setMaximumWidth(560)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(8)

        suspension = widgets.Panel("Muelles y amortiguadores")
        grid = widgets.GridView("Delantero", "Trasero")
        self.spring_front = widgets.dspin(5, 400, 1, 1)
        self.spring_rear = widgets.dspin(5, 400, 1, 1)
        self.bump_front = widgets.dspin(0, 40, 0.1, 2)
        self.bump_rear = widgets.dspin(0, 40, 0.1, 2)
        self.rebound_front = widgets.dspin(0, 40, 0.1, 2)
        self.rebound_rear = widgets.dspin(0, 40, 0.1, 2)
        self.bumpstop_front = widgets.dspin(0, 400, 10, 0)
        self.bumpstop_rear = widgets.dspin(0, 400, 10, 0)
        self.height_front = widgets.dspin(-80, 80, 1, 1)
        self.height_rear = widgets.dspin(-80, 80, 1, 1)
        self.camber_front = widgets.dspin(-10, 2, 0.1, 1)
        self.camber_rear = widgets.dspin(-10, 2, 0.1, 1)

        grid.add_pair(
            "Muelles", self.spring_front, self.spring_rear, "N/mm",
            "SPRING_RATE: rigidez del muelle medida en la rueda (AC lo guarda en N/m)",
        )
        grid.add_pair(
            "Amortiguador compresion", self.bump_front, self.bump_rear, "N·s/mm",
            "DAMP_BUMP: frenado de la suspension al comprimirse",
        )
        grid.add_pair(
            "Amortiguador extension", self.rebound_front, self.rebound_rear, "N·s/mm",
            "DAMP_REBOUND: controla como vuelve la suspension",
        )
        grid.add_pair(
            "Tope de compresion", self.bumpstop_front, self.bumpstop_rear, "N/mm",
            "BUMP_STOP_RATE",
        )
        grid.add_pair(
            "Altura (rod length)", self.height_front, self.height_rear, "mm",
            "ROD_LENGTH: positivo sube el coche, negativo lo baja",
        )
        grid.add_pair(
            "Camber estatico", self.camber_front, self.camber_rear, "grados", "STATIC_CAMBER",
        )
        suspension.add_widget(grid)
        self.setup_note = suspension.add_note("", "info")
        column_layout.addWidget(suspension)

        arb = widgets.Panel("Barras estabilizadoras (ARB)")
        arb_grid = widgets.GridView("Delantera", "Trasera")
        self.arb_front = widgets.dspin(0, 200000, 1000, 0)
        self.arb_rear = widgets.dspin(0, 200000, 1000, 0)
        arb_grid.add_pair("Rigidez", self.arb_front, self.arb_rear, "Nm", "ARB: barra estabilizadora")
        arb.add_widget(arb_grid)
        arb.add_note(
            "Mas barra en un eje = ese eje pierde agarre antes. Delantera mas dura subvira, "
            "trasera mas dura sobrevira.",
            "info",
        )
        column_layout.addWidget(arb)

        brakes = widgets.Panel("Frenos")
        self.brake_torque = widgets.dspin(0, 8000, 50, 0)
        self.brake_bias = widgets.dspin(30, 95, 0.5, 1)
        self.handbrake = widgets.dspin(0, 8000, 50, 0)
        brakes.add("Par maximo total", self.brake_torque, "Nm", "MAX_TORQUE de brakes.ini")
        brakes.add(
            "Reparto delantero", self.brake_bias, "%",
            "FRONT_SHARE: 0.75 en el fichero = 75% de la frenada delante",
        )
        brakes.add("Freno de mano", self.handbrake, "Nm", "HANDBRAKE_TORQUE (solo lectura)")
        self.handbrake.setEnabled(False)
        brakes.add_note(
            "El par total lo reparte el reparto delantero/trasero. Mucho par con poco peso = "
            "bloqueos faciles; el ABS del coche no lo puedes activar desde aqui.",
            "info",
        )
        column_layout.addWidget(brakes)

        weight = widgets.Panel("Peso, combustible y presiones")
        self.mass = widgets.dspin(100, 3000, 1, 0)
        self.max_fuel = widgets.dspin(0, 200, 1, 0)
        self.pressure_front = widgets.dspin(0, 60, 0.1, 1, "PSI", "Presion en frio del compuesto delantero principal")
        self.pressure_rear = widgets.dspin(0, 60, 0.1, 1, "PSI", "Presion en frio del compuesto trasero principal")
        weight.add("Masa total", self.mass, "kg", "TOTALMASS de car.ini (el coche + piloto)")
        weight.add("Deposito maximo", self.max_fuel, "L", "MAX_FUEL de car.ini")
        weight.add("Presion delantera", self.pressure_front, "", "PRESSURE_STATIC del compuesto delantero principal")
        weight.add("Presion trasera", self.pressure_rear, "", "PRESSURE_STATIC del compuesto trasero principal")
        self.weight_note = weight.add_note("", "dato")
        column_layout.addWidget(weight)
        column_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(column)
        root.addWidget(scroll, 0)

        # ------------------------------------------------------------- derecha
        analysis = widgets.Panel("Analisis del reparto")
        self.balance_note = analysis.add_note("", "dato")
        self.frequency_note = analysis.add_note("", "dato")
        self.brake_note = analysis.add_note("", "dato")
        self.power_note = analysis.add_note("", "dato")
        self.hint_note = analysis.add_note("", "info")
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(analysis)
        side_layout.addStretch(1)
        root.addWidget(side, 1)

        for field in self._all_fields():
            field.valueChanged.connect(self._store)
        self._initial_ranges = {
            field: (field.minimum(), field.maximum(), field.singleStep())
            for field in self._all_fields()
        }
        self._initial_ranges.update({
            self.mass: (100, 3000, 1),
            self.max_fuel: (0, 200, 1),
            self.pressure_front: (0, 60, 0.1),
            self.pressure_rear: (0, 60, 0.1),
            self.height_front: (-80, 80, 1),
            self.height_rear: (-80, 80, 1),
            self.arb_front: (0, 200000, 1000),
            self.arb_rear: (0, 200000, 1000),
            self.spring_front: (5, 400, 1),
            self.spring_rear: (5, 400, 1),
            self.bump_front: (0, 40, 0.1),
            self.bump_rear: (0, 40, 0.1),
            self.rebound_front: (0, 40, 0.1),
            self.rebound_rear: (0, 40, 0.1),
            self.bumpstop_front: (0, 400, 10),
            self.bumpstop_rear: (0, 400, 10),
            self.camber_front: (-10, 2, 0.1),
            self.camber_rear: (-10, 2, 0.1),
            self.brake_torque: (0, 8000, 50),
            self.brake_bias: (30, 95, 0.5),
            self.handbrake: (0, 8000, 50),
            self.pressure_front: (0, 60, 0.1),
            self.pressure_rear: (0, 60, 0.1),
        })

    # ------------------------------------------------------------------ util
    def _all_fields(self) -> list:
        return [
            self.spring_front, self.spring_rear, self.bump_front, self.bump_rear,
            self.rebound_front, self.rebound_rear, self.bumpstop_front, self.bumpstop_rear,
            self.height_front, self.height_rear, self.camber_front, self.camber_rear,
            self.arb_front, self.arb_rear, self.brake_torque, self.brake_bias,
            self.mass, self.max_fuel, self.pressure_front, self.pressure_rear,
        ]

    # ------------------------------------------------------------------ carga
    def load(self, car: CarData | None) -> None:
        self.car = car
        self._loading = True
        try:
            for field, (minimum, maximum, step) in self._initial_ranges.items():
                field.setRange(minimum, maximum)
                field.setSingleStep(step)
            available = bool(car is not None and car.editable)
            self.setEnabled(available)
            if not available:
                self.setup_note.setText("")
                self.stats.clear_values()
                for note in (self.balance_note, self.frequency_note, self.brake_note,
                             self.power_note, self.hint_note, self.weight_note):
                    note.setText("")
                return

            self.spring_front.setValue(units.spring_to_nmm(car.spring_rate(True)))
            self.spring_rear.setValue(units.spring_to_nmm(car.spring_rate(False)))
            self.bump_front.setValue(units.damper_to_nsmm(car.damper(True, False)))
            self.bump_rear.setValue(units.damper_to_nsmm(car.damper(False, False)))
            self.rebound_front.setValue(units.damper_to_nsmm(car.damper(True, True)))
            self.rebound_rear.setValue(units.damper_to_nsmm(car.damper(False, True)))
            self.bumpstop_front.setValue(units.spring_to_nmm(car.bump_stop_rate(True)))
            self.bumpstop_rear.setValue(units.spring_to_nmm(car.bump_stop_rate(False)))
            self.height_front.setValue(car.ride_height_offset(True) * 1000.0)
            self.height_rear.setValue(car.ride_height_offset(False) * 1000.0)
            camber = car.ini("suspensions.ini")
            self.camber_front.setValue(camber.get_float("FRONT", "STATIC_CAMBER", 0.0))
            self.camber_rear.setValue(camber.get_float("REAR", "STATIC_CAMBER", 0.0))
            self.arb_front.setValue(car.arb(True))
            self.arb_rear.setValue(car.arb(False))
            self.brake_torque.setValue(car.brake_torque)
            self.brake_bias.setValue(car.brake_bias_percent)
            self.handbrake.setValue(car.handbrake_torque)
            self.mass.setValue(car.mass)
            self.max_fuel.setValue(car.max_fuel)
            self.pressure_front.setValue(car.tyre_pressure(True))
            self.pressure_rear.setValue(car.tyre_pressure(False))

            self._apply_setup_ranges()
            self._refresh_analysis()
        finally:
            self._loading = False

    # (etiqueta, secciones de setup.ini, campo, factor a las unidades de la pestana)
    _SETUP_FIELDS = (
        ("Muelles delanteros", ("SPRING_RATE_LF", "SPRING_RATE_RF"), "spring_front", 1.0),
        ("Muelles traseros", ("SPRING_RATE_LR", "SPRING_RATE_RR"), "spring_rear", 1.0),
        ("Amortiguador comp. del.", ("DAMP_BUMP_LF", "DAMP_BUMP_RF"), "bump_front", 0.001),
        ("Amortiguador comp. tras.", ("DAMP_BUMP_LR", "DAMP_BUMP_RR"), "bump_rear", 0.001),
        ("Amortiguador ext. del.", ("DAMP_REBOUND_LF", "DAMP_REBOUND_RF"), "rebound_front", 0.001),
        ("Amortiguador ext. tras.", ("DAMP_REBOUND_LR", "DAMP_REBOUND_RR"), "rebound_rear", 0.001),
        ("ARB delantera", ("ARB_FRONT",), "arb_front", 1.0),
        ("ARB trasera", ("ARB_REAR",), "arb_rear", 1.0),
        ("Camber delantero", ("CAMBER_LF", "CAMBER_RF"), "camber_front", 1.0),
        ("Camber trasero", ("CAMBER_LR", "CAMBER_RR"), "camber_rear", 1.0),
        ("Reparto de frenada", ("FRONT_BIAS",), "brake_bias", 1.0),
    )

    def _apply_setup_ranges(self) -> None:
        """Rangos que el propio coche declara en setup.ini (los del menu del juego).

        Solo se aplican cuando la unidad coincide con la que se muestra aqui:
        muelles en N/mm, amortiguadores en N·s/m que se pasan a N·s/mm, ARB en Nm,
        camber en grados y reparto de frenada en %. La altura (ROD_LENGTH) usa otra
        escala en cada coche, asi que se queda con el rango del editor.
        """
        if self.car is None:
            return
        applied = []
        for label, names, attribute, factor in self._SETUP_FIELDS:
            rng = self.car.setup_range(*names)
            if rng is None:
                continue
            minimum, maximum, step = (value * factor for value in rng)
            field = getattr(self, attribute)
            if not minimum <= field.value() <= maximum:
                # el coche guarda un valor fuera de su propio rango de setup: mejor no tocarlo
                continue
            field.setRange(minimum, maximum)
            field.setSingleStep(max(step, 10 ** -field.decimals()))
            applied.append(f"{label} {minimum:g}-{maximum:g}")
        self.setup_note.setText(
            "Rangos del setup del coche: " + " · ".join(applied)
            if applied
            else "El coche no declara rangos en setup.ini para estos valores; se usan los del editor."
        )

    # ----------------------------------------------------------------- guardar
    def _store(self) -> None:
        if self._loading or self.car is None:
            return
        self.car.set_spring_rate(True, units.spring_from_nmm(self.spring_front.value()))
        self.car.set_spring_rate(False, units.spring_from_nmm(self.spring_rear.value()))
        self.car.set_damper(True, False, units.damper_from_nsmm(self.bump_front.value()))
        self.car.set_damper(False, False, units.damper_from_nsmm(self.bump_rear.value()))
        self.car.set_damper(True, True, units.damper_from_nsmm(self.rebound_front.value()))
        self.car.set_damper(False, True, units.damper_from_nsmm(self.rebound_rear.value()))
        ini = self.car.ini("suspensions.ini")
        ini.set_value("FRONT", "BUMP_STOP_RATE", units.spring_from_nmm(self.bumpstop_front.value()))
        ini.set_value("REAR", "BUMP_STOP_RATE", units.spring_from_nmm(self.bumpstop_rear.value()))
        self.car.set_ride_height_offset(True, self.height_front.value() / 1000.0)
        self.car.set_ride_height_offset(False, self.height_rear.value() / 1000.0)
        ini.set_value("FRONT", "STATIC_CAMBER", round(self.camber_front.value(), 3))
        ini.set_value("REAR", "STATIC_CAMBER", round(self.camber_rear.value(), 3))
        self.car.set_arb(True, self.arb_front.value())
        self.car.set_arb(False, self.arb_rear.value())
        self.car.brake_torque = self.brake_torque.value()
        self.car.brake_bias_percent = self.brake_bias.value()
        self.car.mass = self.mass.value()
        self.car.max_fuel = self.max_fuel.value()
        self.car.set_tyre_pressure(True, self.pressure_front.value())
        self.car.set_tyre_pressure(False, self.pressure_rear.value())
        self._refresh_analysis()
        self.changed.emit()

    # --------------------------------------------------------------- analisis
    def _refresh_analysis(self) -> None:
        if self.car is None:
            return
        front_k = units.spring_from_nmm(self.spring_front.value())
        rear_k = units.spring_from_nmm(self.spring_rear.value())
        total = front_k + rear_k
        if total > 0:
            front_share = front_k / total * 100.0
            self.balance_note.setText(
                f"Reparto de muelles: {front_share:.1f}% delante / {100 - front_share:.1f}% detras"
            )
        else:
            self.balance_note.setText("")

        frequency = self._natural_frequencies()
        if frequency:
            f_front, f_rear = frequency
            self.frequency_note.setText(
                f"Frecuencia natural: {f_front:.2f} Hz delante · {f_rear:.2f} Hz detras "
                "(un turismo de calle va sobre 1.2 Hz; un GT de carreras, 2.5-4)"
            )
            self.stats.set("front_hz", f"{f_front:.2f}")
            self.stats.set("rear_hz", f"{f_rear:.2f}")
        else:
            self.stats.set("front_hz", "—")
            self.stats.set("rear_hz", "—")
        self.stats.set("mass", f"{self.mass.value():.0f}")

        self.brake_note.setText(
            f"Reparto de frenada: {self.brake_bias.value():.1f}% delante "
            f"({self.brake_torque.value():.0f} Nm totales)"
        )

        hp = self.car.peak_power()[1]
        cv_per_tonne, kg_per_cv = units.power_weight(self.mass.value(), hp)
        self.stats.set("ratio", f"{cv_per_tonne:.0f}")
        self.power_note.setText(
            f"Con {self.mass.value():.0f} kg y {hp:.0f} CV: {cv_per_tonne:.0f} CV/t · "
            f"{kg_per_cv:.2f} kg/CV"
        )
        self.weight_note.setText(
            f"Masa {self.mass.value():.0f} kg · {cv_per_tonne:.0f} CV/t · "
            f"presiones {self.pressure_front.value():.1f}/{self.pressure_rear.value():.1f} PSI en frio"
        )

        if frequency and frequency[1] > frequency[0] * 1.08:
            self.hint_note.setText(
                "El eje trasero esta mucho mas duro que el delantero: el coche tenderá a "
                "sobrevirar en apoyo."
            )
            self.hint_note.setStyleSheet(f"color: {theme.WARN};")
        elif frequency and frequency[0] > frequency[1] * 1.15:
            self.hint_note.setText(
                "El eje delantero esta mas duro: subviraje en apoyo. En traccion delantera es "
                "habitual y ayuda a que el eje motriz trabaje."
            )
            self.hint_note.setStyleSheet(f"color: {theme.INFO};")
        else:
            self.hint_note.setText("Reparto equilibrado entre los dos ejes.")
            self.hint_note.setStyleSheet(f"color: {theme.MUTED};")

    def _natural_frequencies(self) -> tuple[float, float] | None:
        """Frecuencia natural de cada eje (Hz) con la masa repartida al 50% por eje."""
        if self.car is None:
            return None
        mass = self.mass.value()
        cg_front = self.car.cg_front_percent / 100.0 or 0.5
        if mass <= 0:
            return None
        try:
            front = math.sqrt(units.spring_from_nmm(self.spring_front.value()) / (mass * cg_front / 2.0))
            rear = math.sqrt(units.spring_from_nmm(self.spring_rear.value()) / (mass * (1.0 - cg_front) / 2.0))
        except (ValueError, ZeroDivisionError):
            return None
        return (front / (2.0 * math.pi), rear / (2.0 * math.pi))
