"""Pestaña Cambios: relaciones de marcha, grupo final y diferencial."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import theme, widgets
from ..car_data import CarData

MAX_GEARS = 10


class GearboxTab(QWidget):
    """Editor de drivetrain.ini."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.car: CarData | None = None
        self._loading = False
        self._gear_fields: list = []
        self._gear_rows: list[QWidget] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self.stats = widgets.StatRow()
        self.stats.add("gears", "Marchas", "", "accent", "COUNT de drivetrain.ini")
        self.stats.add("final", "Grupo final", "", "info", "FINAL: multiplica todas las marchas")
        self.stats.add(
            "top", "Punta teorica", "km/h", "ok", "Velocidad de la ultima marcha al corte"
        )
        self.stats.add("drive", "Traccion", "", "dato", "TYPE de la seccion [TRACTION]")
        outer.addWidget(self.stats, 0)

        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        outer.addWidget(body, 1)

        # ---------------------------------------------------------- izquierda
        column = QWidget()
        column.setMaximumWidth(430)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(8)

        self.gears_panel = widgets.Panel("Caja de cambios")
        self.drive_label = self.gears_panel.add_note("", "dato")
        self.count = widgets.ispin(
            1, MAX_GEARS, 1, "", "COUNT: numero de marchas que usa AC (las claves de mas se ignoran)"
        )
        self.count.setToolTip("COUNT: numero de marchas que usa AC")
        self.gears_panel.add("Numero de marchas", self.count, "")

        gears_holder = QWidget()
        self.gear_slot = QVBoxLayout(gears_holder)
        self.gear_slot.setContentsMargins(0, 0, 0, 0)
        self.gear_slot.setSpacing(3)
        for index in range(MAX_GEARS):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(f"{index + 1}a")
            label.setMinimumWidth(28)
            row_layout.addWidget(label)
            row_layout.addStretch(1)
            field = widgets.dspin(0.3, 8.0, 0.001, 3)
            field.valueChanged.connect(self._store)
            row_layout.addWidget(field)
            self._gear_fields.append(field)
            self._gear_rows.append(row)
            self.gear_slot.addWidget(row)
        self.gears_panel.add_widget(gears_holder)

        self.reverse = widgets.dspin(-8.0, -0.3, 0.01, 3)
        self.final = widgets.dspin(0.5, 8.0, 0.001, 3)
        self.reverse.valueChanged.connect(self._store)
        self.final.valueChanged.connect(self._store)
        self.gears_panel.add("Marcha atras", self.reverse, "")
        self.gears_panel.add("Grupo final", self.final, "")
        self.gearset_note = self.gears_panel.add_note("", "info")
        column_layout.addWidget(self.gears_panel)

        diff_panel = widgets.Panel("Diferencial")
        self.diff_power = widgets.dspin(
            0, 100, 1, 0, "", "POWER: bloqueo del diferencial al acelerar (0 = abierto)"
        )
        self.diff_coast = widgets.dspin(
            0, 100, 1, 0, "", "COAST: bloqueo al levantar el pie (mas = mas estable al frenar)"
        )
        self.diff_preload = widgets.dspin(0, 200, 1, 0, "", "PRELOAD: par de precarga en Nm")
        for key in ("diff_power", "diff_coast", "diff_preload"):
            getattr(self, key).valueChanged.connect(self._store)
        diff_panel.add("Bloqueo en aceleracion", self.diff_power, "%")
        diff_panel.add("Bloqueo al retener", self.diff_coast, "%")
        diff_panel.add("Precarga", self.diff_preload, "Nm")
        self.clutch_note = diff_panel.add_note("", "info")
        column_layout.addWidget(diff_panel)

        howto = widgets.Panel("Como se comporta")
        howto.add_note(
            "Relaciones mas cortas (numeros mas altos) = mas aceleracion y menos punta. "
            "El grupo final multiplica todas las marchas a la vez.",
            "info",
        )
        self.ratio_note = howto.add_note("", "dato")
        column_layout.addWidget(howto)
        column_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(column)
        root.addWidget(scroll, 0)

        # ------------------------------------------------------------- derecha
        self.ratio_table = widgets.Panel("Relaciones y punta teórica")
        self.ratio_table.add_note(
            "Velocidad calculada a partir del radio de rueda, relación, grupo final y limitador; "
            "no es una medición en pista.", "info"
        )
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.setStyleSheet(f"color: {theme.MUTED};")
        self.ratio_table.add_widget(self.status)
        root.addWidget(self.ratio_table, 1)

        self.count.valueChanged.connect(self._on_count)

    # ------------------------------------------------------------------ carga
    def load(self, car: CarData | None) -> None:
        self.car = car
        self._loading = True
        try:
            available = bool(car is not None and car.editable)
            self.setEnabled(available)
            if not available:
                self.status.setText("")
                self.stats.clear_values()
                self.drive_label.setText("")
                return
            self.count.setValue(car.gear_count)
            for index, field in enumerate(self._gear_fields, start=1):
                field.setValue(car.gear_ratios()[index - 1] if index <= car.gear_count else 1.0)
            self.reverse.setValue(car.reverse_ratio)
            self.final.setValue(car.final_drive)
            power, coast, preload = car.differential
            self.diff_power.setValue(power * 100.0)
            self.diff_coast.setValue(coast * 100.0)
            self.diff_preload.setValue(preload)
            self.drive_label.setText(
                f"Traccion {car.drive_type} · neumatico motriz de "
                f"{car.driven_wheel_radius() * 1000:.0f} mm de radio"
            )
            clutch = car.clutch_max_torque
            self.clutch_note.setText(
                f"Par maximo del embrague: {clutch:.0f} Nm" if clutch else "El coche no define MAX_TORQUE de embrague."
            )
            gearset = car.ratios_rto
            if gearset is not None:
                self.gearset_note.setText(
                    f"ratios.rto: este coche trae un gearset con {gearset.count} relaciones. "
                    "El setup elige entre ellas; aqui se edita la relacion de serie."
                )
                self.gearset_note.setStyleSheet(f"color: {theme.WARN};")
            else:
                self.gearset_note.setText("")
            self._update_visibility()
        finally:
            self._loading = False
        self._draw()

    # ----------------------------------------------------------------- guardar
    def _on_count(self) -> None:
        if self._loading or self.car is None:
            return
        self.car.set_gear_count(self.count.value())
        self._update_visibility()
        self._store()

    def _store(self) -> None:
        if self._loading or self.car is None:
            return
        count = self.count.value()
        for index, field in enumerate(self._gear_fields[:count], start=1):
            self.car.set_gear(index, field.value())
        self.car.reverse_ratio = self.reverse.value()
        self.car.final_drive = self.final.value()
        self.car.set_differential(
            self.diff_power.value() / 100.0,
            self.diff_coast.value() / 100.0,
            self.diff_preload.value(),
        )
        self._draw()
        self.changed.emit()

    def _update_visibility(self) -> None:
        count = self.count.value()
        for index, row in enumerate(self._gear_rows):
            row.setVisible(index < count)

    # ------------------------------------------------------------ actualización
    def _draw(self) -> None:
        if self.car is None or not self.car.editable:
            self.stats.clear_values()
            self.status.setText("")
            return

        limiter = max(self.car.limiter, 500)
        final_drive = self.car.final_drive
        ratios = self.car.gear_ratios()
        top = 0.0
        texts = []

        for index, ratio in enumerate(ratios, start=1):
            speed = self.car.top_speed_kmh(ratio, limiter)
            top = max(top, speed)
            texts.append(f"{index}a: {speed:.0f} km/h")

        self.stats.set("gears", f"{len(ratios)}")
        self.stats.set("final", f"{final_drive:.2f}")
        self.stats.set("top", f"{top:.0f}")
        self.stats.set("drive", self.car.drive_type)

        ratio_text = " · ".join(f"{r:.3f}" for r in ratios)
        self.status.setText(
            f"A {limiter} rpm · grupo final {final_drive:.3f} · relaciones {ratio_text}\n"
            + "   ".join(texts)
        )
