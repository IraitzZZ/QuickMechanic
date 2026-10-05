"""Pestaña Cambios: relaciones de marcha, grupo final y diferencial."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
)

from ..qt_i18n import QLabel, QScrollArea, QWidget

from .. import i18n, theme, widgets
from ..car_data import AWD_KEYS, CarData

MAX_GEARS = 10

# Filas del panel de traccion total: (clave, etiqueta, unidad, ayuda).
# Solo se muestran las claves que el coche ya trae escritas en drivetrain.ini.
AWD_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("FRONT_SHARE", "Reparto al eje delantero", "%",
     "FRONT_SHARE: porcentaje de par que va al eje delantero"),
    ("FRONT_DIFF_POWER", "Bloqueo del. al acelerar", "%",
     "FRONT_DIFF_POWER: bloqueo del diferencial delantero al acelerar (1.0 = 100%)"),
    ("FRONT_DIFF_COAST", "Bloqueo del. al retener", "%",
     "FRONT_DIFF_COAST: bloqueo delantero al levantar el pie"),
    ("FRONT_DIFF_PRELOAD", "Precarga delantera", "Nm",
     "FRONT_DIFF_PRELOAD: par de precarga del diferencial delantero"),
    ("CENTRE_DIFF_POWER", "Bloqueo central al acelerar", "%",
     "CENTRE_DIFF_POWER: bloqueo del diferencial central al acelerar"),
    ("CENTRE_DIFF_COAST", "Bloqueo central al retener", "%",
     "CENTRE_DIFF_COAST: bloqueo central al levantar el pie"),
    ("CENTRE_DIFF_PRELOAD", "Precarga central", "Nm",
     "CENTRE_DIFF_PRELOAD: par de precarga del diferencial central"),
    ("CENTRE_RAMP_TORQUE", "Rampa del central", "Nm",
     "CENTRE_RAMP_TORQUE: par a partir del cual el central empieza a bloquear (modelo [AWD2])"),
    ("CENTRE_MAX_TORQUE", "Par máximo del central", "Nm",
     "CENTRE_MAX_TORQUE: par maximo que puede transmitir el central (modelo [AWD2])"),
    ("REAR_DIFF_POWER", "Bloqueo tras. al acelerar", "%",
     "REAR_DIFF_POWER: bloqueo del diferencial trasero al acelerar"),
    ("REAR_DIFF_COAST", "Bloqueo tras. al retener", "%",
     "REAR_DIFF_COAST: bloqueo trasero al levantar el pie"),
    ("REAR_DIFF_PRELOAD", "Precarga trasera", "Nm",
     "REAR_DIFF_PRELOAD: par de precarga del diferencial trasero"),
)
AWD_FRACTION_HINTS = ("DIFF_POWER", "DIFF_COAST")


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

        # -------------------------------------------------- traccion total (AWD)
        self.awd_panel = widgets.Panel("Tracción total (AWD)")
        self.awd_note = self.awd_panel.add_note("", "info")
        awd_holder = QWidget()
        self.awd_grid = QGridLayout(awd_holder)
        self.awd_grid.setContentsMargins(0, 0, 0, 0)
        self.awd_grid.setHorizontalSpacing(8)
        self.awd_grid.setVerticalSpacing(3)
        self.awd_panel.add_widget(awd_holder)
        self.awd_status = self.awd_panel.add_note("", "dato")
        self.awd_panel.hide()
        column_layout.addWidget(self.awd_panel)
        self._awd_fields: dict[tuple[str, str], object] = {}

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
            self._load_awd(car)
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

    # ------------------------------------------------------ traccion total (AWD)
    def _load_awd(self, car: CarData) -> None:
        """Muestra los parametros AWD que el coche ya declara; nada inventado."""
        widgets.clear_layout(self.awd_grid)
        self._awd_fields.clear()
        sections = car.awd_sections
        if not sections:
            self.awd_panel.hide()
            return
        values = car.awd_values()
        self.awd_panel.show()
        if not values:
            self.awd_note.setText(
                "Este coche declara traccion total, pero drivetrain.ini no trae los parametros "
                "[AWD]/[AWD2]. Para no romper la fisica no se crean claves nuevas."
            )
            self.awd_status.setText("")
            return
        mode = ", ".join(f"[{name}]" for name in sections)
        self.awd_note.setText(
            f"{mode} · solo se editan los parametros que este coche ya trae en drivetrain.ini."
        )
        row = 0
        for section in sections:
            # Cada seccion ([AWD] y, si existe, [AWD2]) lleva su propio bloque.
            header = QLabel(f"[{section}]")
            header.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
            self.awd_grid.addWidget(header, row, 0, 1, 3)
            row += 1
            for key in AWD_KEYS:
                value = car.awd_value(section, key)
                if value is None:
                    continue
                label, unit, tip = self._awd_row_meta(key)
                field = widgets.dspin(*self._awd_field_range(key), unit, tip)
                fraction = key.endswith(AWD_FRACTION_HINTS)
                field.setValue(value * 100.0 if fraction else value)
                field.valueChanged.connect(
                    lambda _value=0.0, s=section, k=key, f=field, p=fraction: self._store_awd(s, k, f, p)
                )
                self.awd_grid.addWidget(QLabel(label), row, 0)
                self.awd_grid.addWidget(field, row, 1)
                self.awd_grid.addWidget(QLabel(unit), row, 2)
                self._awd_fields[(section, key)] = field
                row += 1
        self._refresh_awd_status()

    @staticmethod
    def _awd_row_meta(key: str) -> tuple[str, str, str]:
        for row_key, label, unit, tip in AWD_ROWS:
            if row_key == key:
                return label, unit, tip
        return key, "", ""

    @staticmethod
    def _awd_field_range(key: str) -> tuple[float, float, float, int]:
        """Rango del campo. Los bloqueos se editan en % y las precargas en Nm."""
        if key.endswith(AWD_FRACTION_HINTS):
            return 0.0, 100.0, 1.0, 0
        if key == "FRONT_SHARE":
            return 0.0, 100.0, 1.0, 0
        if key in {"CENTRE_RAMP_TORQUE", "CENTRE_MAX_TORQUE"}:
            return 0.0, 10000.0, 10.0, 0
        return 0.0, 1000.0, 5.0, 0

    def _store_awd(self, section: str, key: str, field, fraction: bool) -> None:
        if self._loading or self.car is None:
            return
        value = float(field.value()) / 100.0 if fraction else float(field.value())
        if not self.car.set_awd_value(section, key, value):
            return
        self._refresh_awd_status()
        self.changed.emit()

    def _refresh_awd_status(self) -> None:
        car = self.car
        if car is None or not car.awd_sections:
            self.awd_status.setText("")
            return
        pieces: list[str] = []
        for section in car.awd_sections:
            share = car.awd_value(section, "FRONT_SHARE")
            if share is not None:
                pieces.append(i18n.tr("{}% al eje delantero", f"{share:.0f}"))
            ramp = car.awd_value(section, "CENTRE_RAMP_TORQUE")
            if ramp is not None:
                pieces.append(i18n.tr("rampa central {} Nm", f"{ramp:.0f}"))
            top = car.awd_value(section, "CENTRE_MAX_TORQUE")
            if top is not None:
                pieces.append(i18n.tr("par máximo central {} Nm", f"{top:.0f}"))
        self.awd_status.setText(" · ".join(pieces))

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
