"""Resumen de biblioteca y métricas calculadas, sin gráficos ni telemetría ficticia."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout
from ..qt_i18n import QLabel, QLineEdit, QPushButton, QWidget

from .. import theme, widgets
from ..ac_scanner import Car
from ..car_data import CarData


class DashboardTab(QWidget):
    """Dashboard con datos de archivos locales y cálculos identificados como tales."""

    carRequested = pyqtSignal(str)  # carpeta del coche
    toolRequested = pyqtSignal(int)  # índice de pestaña
    searchRequested = pyqtSignal(str)  # texto de búsqueda inicial
    actionRequested = pyqtSignal(str)  # acción rápida: palette, random, export, sync

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        layout.addWidget(self._build_home())

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
        self.set_home([], [], [])

    def _build_home(self) -> QWidget:
        """Cabecera de inicio: búsqueda, acciones rápidas y accesos a recientes y favoritos."""
        home = QWidget()
        home_layout = QVBoxLayout(home)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(10)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar herramienta o acción… (Enter)")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._emit_search)
        search_row.addWidget(self.search, 1)
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(lambda _checked=False: self._emit_search())
        search_row.addWidget(search_button)
        home_layout.addLayout(search_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        for key, label, tip in (
            ("palette", "Todas las herramientas", "Abrir el buscador de herramientas (Ctrl+K)"),
            ("random", "Coche aleatorio", "Elegir al azar un coche de la lista (Ctrl+Shift+N)"),
            ("export", "Exportar CSV", "Exportar la biblioteca visible a CSV (Ctrl+E)"),
            ("sync", "Sincronizar biblioteca", "Volver a leer la carpeta de coches de Assetto Corsa"),
        ):
            button = QPushButton(label)
            button.setObjectName("ghost")
            button.setToolTip(tip)
            button.clicked.connect(lambda _checked=False, action=key: self.actionRequested.emit(action))
            actions.addWidget(button)
        actions.addStretch(1)
        home_layout.addLayout(actions)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.recent_panel, self._recent_box = self._card("Coches recientes")
        self.favorite_panel, self._favorite_box = self._card("Favoritos")
        self.tools_panel, self._tools_box = self._card("Herramientas recientes")
        for panel in (self.recent_panel, self.favorite_panel, self.tools_panel):
            cards.addWidget(panel, 1)
        home_layout.addLayout(cards)
        return home

    def _card(self, title: str) -> tuple[widgets.Panel, QVBoxLayout]:
        panel = widgets.Panel(title)
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        panel.add_widget(holder)
        return panel, box

    def _emit_search(self) -> None:
        self.searchRequested.emit(self.search.text().strip())

    def set_home(
        self,
        recent: list[tuple[str, str]],
        favorites: list[tuple[str, str]],
        tools: list[tuple[int, str]],
    ) -> None:
        """Rellena las tarjetas de inicio. Cada entrada es (valor para la señal, texto del botón)."""
        self._fill_card(self._recent_box, recent, "Abre un coche para verlo aquí.", self.carRequested)
        self._fill_card(self._favorite_box, favorites, "Marca coches con ★ para fijarlos aquí.", self.carRequested)
        self._fill_card(self._tools_box, tools, "Las herramientas que abras aparecerán aquí.", self.toolRequested)

    def _fill_card(self, box: QVBoxLayout, items: list, empty: str, signal) -> None:
        while box.count():
            item = box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not items:
            hint = QLabel(empty)
            hint.setObjectName("pageDescription")
            hint.setWordWrap(True)
            box.addWidget(hint)
            box.addStretch(1)
            return
        for value, text in items[:6]:
            button = QPushButton(text)
            button.setObjectName("homeLink")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, v=value, s=signal: s.emit(v))
            box.addWidget(button)
        box.addStretch(1)

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
