"""Resumen de biblioteca y métricas calculadas, sin gráficos ni telemetría ficticia."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QVBoxLayout
from ..qt_i18n import QLabel, QWidget

from .. import theme, widgets
from ..ac_scanner import Car
from ..car_data import CarData


class DashboardTab(QWidget):
    """Dashboard con datos de archivos locales y cálculos identificados como tales."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.library_stats = widgets.StatRow()
        self.library_stats.add("installed", "Coches instalados", "", "accent")
        self.library_stats.add("editable", "Con data/", "", "ok")
        self.library_stats.add("locked", "Con data.acd", "", "aviso")
        self.library_stats.add("skins", "Skins", "", "info", "Skins detectadas en la biblioteca")
        layout.addWidget(self.library_stats)

        self.car_stats = widgets.StatRow()
        self.car_stats.add("power", "Potencia calculada", "CV", "ok", "Estimación matemática derivada de power.lut, no telemetría de pista")
        self.car_stats.add("torque", "Par calculado", "Nm", "accent")
        self.car_stats.add("mass", "Masa", "kg", "info")
        self.car_stats.add("ratio", "Rel. peso/potencia", "CV/t", "aviso")
        layout.addWidget(self.car_stats)

        details = QWidget()
        grid = QGridLayout(details)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        self.engine_panel = widgets.Panel("Resumen calculado del motor")
        self.engine_text = QLabel("Selecciona un coche editable.")
        self.engine_text.setWordWrap(True)
        self.engine_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.engine_panel.add_widget(self.engine_text)
        self.gear_panel = widgets.Panel("Velocidad teórica por marcha")
        self.gear_text = QLabel("Se calcula con relación, grupo final, radio de rueda y limitador.")
        self.gear_text.setWordWrap(True)
        self.gear_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.gear_panel.add_widget(self.gear_text)
        grid.addWidget(self.engine_panel, 0, 0)
        grid.addWidget(self.gear_panel, 0, 1)
        layout.addWidget(details, 1)

        self.alerts = widgets.Panel("Comprobaciones del fichero")
        self.alert_text = QLabel("Selecciona un coche editable para ver comprobaciones locales.")
        self.alert_text.setWordWrap(True)
        self.alert_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.alerts.add_widget(self.alert_text)
        layout.addWidget(self.alerts)
        self._set_no_car()
        self.set_library([])

    def set_library(self, cars: list[Car]) -> None:
        editable = sum(car.editable for car in cars)
        locked = sum(car.has_acd and not car.editable for car in cars)
        skin_count = 0
        for car in cars:
            try:
                skin_count += sum(1 for entry in (car.folder / "skins").iterdir() if entry.is_dir())
            except OSError:
                continue
        self.library_stats.set("installed", str(len(cars)))
        self.library_stats.set("editable", str(editable))
        self.library_stats.set("locked", str(locked))
        self.library_stats.set("skins", str(skin_count))

    def load(self, car: CarData | None) -> None:
        if car is None or not car.editable:
            self._set_no_car()
            return
        rpm_torque, torque = car.peak_torque()
        rpm_power, power = car.peak_power()
        cv_per_tonne, _kg_per_cv = car.power_weight()
        self.car_stats.set("power", f"{power:.0f}")
        self.car_stats.set("torque", f"{torque:.0f}")
        self.car_stats.set("mass", f"{car.mass:.0f}")
        self.car_stats.set("ratio", f"{cv_per_tonne:.0f}")
        self.engine_text.setText(
            f"Pico de par leído: {torque:.1f} Nm a {rpm_torque:.0f} rpm\n"
            f"Potencia calculada desde par y rpm: {power:.1f} CV a {rpm_power:.0f} rpm\n"
            f"Limitador configurado: {car.limiter} rpm · masa: {car.mass:.0f} kg\n\n"
            "Son cálculos a partir de los archivos del coche; no son datos medidos en pista."
        )
        speeds = car.gear_top_speeds()
        self.gear_text.setText("   ·   ".join(
            f"{index}ª: {speed:.0f} km/h" for index, speed in enumerate(speeds, start=1)
        ) or "No hay relaciones de cambio disponibles.")
        labels = {"peligro": "URGENTE", "aviso": "AVISO", "info": "INFO"}
        lines = [
            f"<span style='color:{theme.TONE_COLORS.get(level, theme.MUTED)}'><b>{labels.get(level, level.upper())}</b></span>  {text}"
            for level, text in car.alerts()[:6]
        ]
        self.alert_text.setText("<br><br>".join(lines))

    def _set_no_car(self) -> None:
        self.car_stats.clear_values()
        self.engine_text.setText("Selecciona un coche editable para revisar las cifras del archivo.")
        self.gear_text.setText("Las velocidades teóricas aparecerán aquí; no se muestran gráficas.")
        self.alert_text.setText("Selecciona un coche editable para ver comprobaciones locales.")
