"""Pestana Taller: analisis, gearing, setups, versiones, respaldos e informes.

Reune en un sitio las herramientas que no son edicion directa de un .ini:
estimacion de prestaciones, comparador de coches, simulador de cambio, gearing
optimo, presets de estilo, gestor de setups y versiones, respaldos, historial de
cambios y exportacion de informes.

La pestana **nunca escribe en disco por su cuenta**: todo pasa por ``CarData`` y
por ``garage``, y el guardado sigue siendo cosa del boton de la barra inferior.
"""
from __future__ import annotations

import html
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from ..qt_i18n import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from .. import analysis, curves, garage, i18n, theme, units, widgets
from ..car_data import CarData

SPEEDS = "km/h"


class LabTab(QWidget):
    """Analisis y gestion del coche: prestaciones, setups y respaldos."""

    changed = pyqtSignal()
    carReloaded = pyqtSignal()
    libraryChanged = pyqtSignal()
    status = pyqtSignal(str)

    #: Ficheros que enseña el inspector (ademas de los de fisica obligatorios).
    INSPECTOR_FILES = (
        "engine.ini", "drivetrain.ini", "suspensions.ini", "tyres.ini", "brakes.ini",
        "car.ini", "setup.ini", "aero.ini", "electronics.ini", "damage.ini", "drs.ini",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.car: CarData | None = None
        self.car_folder: Path | None = None
        self._quick_keys: dict[str, bool] = {}
        self._library: list = []
        self._meta_cache: dict = {}
        self._favorites: set[str] = set()
        self._loading = False
        self._stats_ready = False
        self._gearing_plan = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self.stats = widgets.StatRow()
        self.stats.add("zero100", "0-100 km/h", "s", "accent", "Simulacion cuasi-estatica con la curva de par actual")
        self.stats.add("zero200", "0-200 km/h", "s", "info", "Misma simulacion hasta 200 km/h")
        self.stats.add("top", "Punta estimada", SPEEDS, "ok", "Velocidad donde la fuerza iguala la resistencia")
        self.stats.add("pw", "Peso/potencia", "", "dato", "CV por tonelada y kg por CV")
        self.stats.add("accel", "Aceleracion", "g", "info", "Aceleracion longitudinal maxima estimada")
        outer.addWidget(self.stats, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_analysis_column())
        splitter.addWidget(self._build_management_column())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

    # ------------------------------------------------------------------ columnas
    def _build_analysis_column(self) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(8)

        # ---------------------------------------------------------- curva editable
        panel = widgets.Panel("Curva del motor · arrastra los puntos para editarla")
        self.curve_mode = QComboBox()
        self.curve_mode.addItem("Par (power.lut)", "torque")
        self.curve_mode.addItem("Potencia (CV)", "power")
        self.curve_mode.addItem("Frenada en rueda", "brake")
        self.curve_mode.currentIndexChanged.connect(self._refresh_curve)
        panel.add("Curva", self.curve_mode, "")
        self.curve = curves.CurveEditor()
        self.curve.x_label = "rpm"
        self.curve.y_label = "Nm"
        self.curve.unit = "Nm"
        self.curve.pointChanged.connect(self._on_curve_point)
        panel.add_widget(self.curve)
        self.curve_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # -------------------------------------------------------- simulador cambio
        panel = widgets.Panel("Simulador de cambio · velocidad por marcha")
        self.gear_chart = curves.LineChart()
        self.gear_chart.x_label = "km/h"
        self.gear_chart.y_label = "rpm"
        panel.add_widget(self.gear_chart)
        self.gear_legend = curves.Legend()
        panel.add_widget(self.gear_legend)
        self.gear_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # ------------------------------------------------------------ gearing
        panel = widgets.Panel("Gearing optimo")
        self.circuit = QComboBox()
        self.circuit.addItem("Auto (según potencia)", 0.0)
        for name, speed in analysis.CIRCUIT_PROFILES.items():
            self.circuit.addItem(f"{name} · {speed:.0f} km/h", float(speed))
        panel.add("Circuito", self.circuit, "")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        self.gearing_calc = QPushButton("Calcular relaciones")
        self.gearing_calc.clicked.connect(self._calculate_gearing)
        self.gearing_apply = QPushButton("Aplicar a drivetrain.ini")
        self.gearing_apply.setObjectName("ghost")
        self.gearing_apply.clicked.connect(self._apply_gearing)
        self.gearing_apply.setEnabled(False)
        row_layout.addWidget(self.gearing_calc)
        row_layout.addWidget(self.gearing_apply)
        row_layout.addStretch(1)
        panel.add_widget(row)
        self.gearing_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # ---------------------------------------------------------- comparador
        panel = widgets.Panel("Comparador de coches")
        self.rival = QComboBox()
        panel.add("Comparar con", self.rival, "")
        compare_button = QPushButton("Comparar")
        compare_button.clicked.connect(self._compare)
        panel.add_widget(compare_button)
        self.compare_view = QTextBrowser()
        self.compare_view.setMinimumHeight(210)
        panel.add_widget(self.compare_view)
        layout.addWidget(panel)

        # --------------------------------------------------------- diagnostico
        panel = widgets.Panel("Diagnostico visual y conflictos")
        self.diagnostic_view = QTextBrowser()
        self.diagnostic_view.setMinimumHeight(190)
        panel.add_widget(self.diagnostic_view)
        refresh = QPushButton("Revisar de nuevo")
        refresh.clicked.connect(self._refresh_diagnostics)
        panel.add_widget(refresh)
        layout.addWidget(panel)

        layout.addStretch(1)
        area.setWidget(holder)
        return area

    def _build_management_column(self) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ------------------------------------------------------------ presets
        panel = widgets.Panel("Presets de estilo")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(5)
        self.style_buttons = {}
        for index, (key, label) in enumerate(analysis.STYLE_LABELS.items()):
            button = QPushButton(label)
            button.setObjectName("ghost")
            button.setToolTip(f"Aplica el preset {label} solo sobre los campos que el coche ya declara")
            button.clicked.connect(lambda _checked=False, style=key: self._apply_style(style))
            grid.addWidget(button, index // 3, index % 3)
            self.style_buttons[key] = button
        panel.add_widget(_grid_holder(grid))
        self.style_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # ------------------------------------------------- ajustes rapidos
        panel = widgets.Panel("Ajustes rapidos (solo claves existentes)")
        panel.add_separator()
        self.pressure_front = widgets.dspin(15.0, 50.0, 0.5, 1, "PSI", "PRESSURE_STATIC del eje delantero")
        self.pressure_rear = widgets.dspin(15.0, 50.0, 0.5, 1, "PSI", "PRESSURE_STATIC del eje trasero")
        self.brake_bias = widgets.dspin(40.0, 85.0, 0.5, 1, "%", "FRONT_SHARE: reparto de frenada al eje delantero")
        self.brake_torque = widgets.dspin(0.0, 8000.0, 50.0, 0, "Nm", "MAX_TORQUE de brakes.ini")
        self.ride_front = widgets.dspin(-0.1, 0.1, 0.005, 3, "m", "ROD_LENGTH del eje delantero (altura libre)")
        self.ride_rear = widgets.dspin(-0.1, 0.1, 0.005, 3, "m", "ROD_LENGTH del eje trasero")
        self.quick_note = panel.add_note("", "info")
        for label, field, unit, tip in (
            ("Presion delantera", self.pressure_front, "PSI", "Neumaticos delanteros"),
            ("Presion trasera", self.pressure_rear, "PSI", "Neumaticos traseros"),
            ("Reparto de freno", self.brake_bias, "%", "FRONT_SHARE de brakes.ini"),
            ("Par de frenado", self.brake_torque, "Nm", "MAX_TORQUE de brakes.ini"),
            ("Altura delantera", self.ride_front, "m", "ROD_LENGTH delantero"),
            ("Altura trasera", self.ride_rear, "m", "ROD_LENGTH trasero"),
        ):
            field.valueChanged.connect(self._store_quick)
            panel.add(label, field, unit, tip)
        panel.add_separator()
        self.aero_combo = QComboBox()
        self.aero_value = widgets.dspin(-1000.0, 1000.0, 0.01, 3, "", "Valor del parametro de aero.ini elegido")
        self.aero_combo.currentIndexChanged.connect(self._sync_aero_value)
        panel.add("Aero (aero.ini)", self.aero_combo, "")
        panel.add("Valor", self.aero_value, "")
        aero_apply = QPushButton("Aplicar valor de aero")
        aero_apply.setObjectName("ghost")
        aero_apply.clicked.connect(self._store_aero)
        panel.add_widget(aero_apply)
        self.aero_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # -------------------------------------------------------- inspector .ini
        panel = widgets.Panel("Inspector de datos .ini (solo lectura)")
        self.inspector_filter = QLineEdit()
        self.inspector_filter.setPlaceholderText("Filtrar por fichero, seccion, clave o valor…")
        self.inspector_filter.setClearButtonEnabled(True)
        self.inspector_filter.textChanged.connect(self._queue_inspector)
        panel.add("Localizar", self.inspector_filter, "")
        self._inspector_timer = QTimer(self)
        self._inspector_timer.setSingleShot(True)
        self._inspector_timer.setInterval(220)
        self._inspector_timer.timeout.connect(self._refresh_inspector)
        self.inspector_view = QTextBrowser()
        self.inspector_view.setMinimumHeight(190)
        panel.add_widget(self.inspector_view)
        panel.add_note(
            "Solo lectura: aqui se mira el valor tal cual esta en el .ini, sin tocar nada.",
            "info",
        )
        layout.addWidget(panel)

        # ------------------------------------------------------- setup manager
        panel = widgets.Panel("Setup Manager · por circuito y condiciones")
        self.setup_name = QLineEdit()
        self.setup_name.setPlaceholderText("Nombre del setup")
        self.setup_circuit = QComboBox()
        self.setup_circuit.setEditable(True)
        self.setup_circuit.addItem("")
        for name in analysis.CIRCUIT_PROFILES:
            self.setup_circuit.addItem(name)
        self.setup_conditions = QLineEdit()
        self.setup_conditions.setPlaceholderText("seco, lluvia, 25 °C…")
        self.setup_style = QComboBox()
        self.setup_style.addItem("(sin estilo)", "")
        for key, label in analysis.STYLE_LABELS.items():
            self.setup_style.addItem(label, key)
        panel.add("Nombre", self.setup_name, "")
        panel.add("Circuito", self.setup_circuit, "")
        panel.add("Condiciones", self.setup_conditions, "")
        panel.add("Estilo", self.setup_style, "")
        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        for text, slot in (
            ("Guardar", self._save_setup),
            ("Cargar", self._load_setup),
            ("Borrar", self._delete_setup),
            ("Exportar", self._export_setup),
            ("Importar", self._import_setup),
        ):
            button = QPushButton(text)
            button.setObjectName("ghost")
            button.clicked.connect(slot)
            buttons_layout.addWidget(button)
        panel.add_widget(buttons)
        self.setup_list = QListWidget()
        self.setup_list.setMinimumHeight(110)
        panel.add_widget(self.setup_list)
        layout.addWidget(panel)

        # -------------------------------------------------------------- clonado
        panel = widgets.Panel("Clonar coche")
        self.clone_name = QLineEdit()
        self.clone_name.setPlaceholderText("nombre de la carpeta nueva (opcional)")
        panel.add("Carpeta destino", self.clone_name, "")
        self.clone_button = QPushButton("Clonar este coche")
        self.clone_button.setObjectName("ghost")
        self.clone_button.setToolTip(
            "Copia entera del coche en content/cars con otro nombre; el original no se toca"
        )
        self.clone_button.clicked.connect(self._clone_car)
        panel.add_widget(self.clone_button)
        self.clone_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # ------------------------------------------------------------ versiones
        panel = widgets.Panel("Gestor de versiones")
        self.version_label = QLineEdit()
        self.version_label.setPlaceholderText("Etiqueta de la version")
        panel.add("Etiqueta", self.version_label, "")
        version_buttons = QWidget()
        version_layout = QHBoxLayout(version_buttons)
        version_layout.setContentsMargins(0, 0, 0, 0)
        for text, slot in (
            ("Guardar version", self._save_version),
            ("Restaurar", self._restore_version),
            ("Borrar", self._delete_version),
        ):
            button = QPushButton(text)
            button.setObjectName("ghost")
            button.clicked.connect(slot)
            version_layout.addWidget(button)
        panel.add_widget(version_buttons)
        self.version_list = QListWidget()
        self.version_list.setMinimumHeight(100)
        panel.add_widget(self.version_list)
        layout.addWidget(panel)

        # ------------------------------------------------------------- respaldos
        panel = widgets.Panel("Respaldos y backup inteligente")
        self.backup_list = QListWidget()
        self.backup_list.setMinimumHeight(110)
        panel.add_widget(self.backup_list)
        backup_buttons = QWidget()
        backup_layout = QHBoxLayout(backup_buttons)
        backup_layout.setContentsMargins(0, 0, 0, 0)
        for text, slot in (
            ("Crear respaldo", self._create_backup),
            ("Restaurar fichero", self._restore_member),
            ("Limpiar antiguos", self._prune_backups),
            ("Actualizar", self._refresh_backups),
        ):
            button = QPushButton(text)
            button.setObjectName("ghost")
            button.clicked.connect(slot)
            backup_layout.addWidget(button)
        panel.add_widget(backup_buttons)
        self.backup_note = panel.add_note("", "info")
        layout.addWidget(panel)

        # -------------------------------------------------------- informe y stats
        panel = widgets.Panel("Informe, historial y estadisticas")
        report_buttons = QWidget()
        report_layout = QHBoxLayout(report_buttons)
        report_layout.setContentsMargins(0, 0, 0, 0)
        for text, fmt in (("Exportar .txt", "txt"), ("Exportar .html", "html")):
            button = QPushButton(text)
            button.setObjectName("ghost")
            button.clicked.connect(lambda _checked=False, kind=fmt: self._export_report(kind))
            report_layout.addWidget(button)
        panel.add_widget(report_buttons)
        panel.add_separator()
        panel.add_widget(_heading("Historial de cambios"))
        self.history_view = QTextBrowser()
        self.history_view.setMinimumHeight(130)
        panel.add_widget(self.history_view)
        panel.add_separator()
        self.library_stats = widgets.StatRow()
        self.library_stats.setMinimumHeight(90)
        panel.add_widget(self.library_stats)
        layout.addWidget(panel)

        layout.addStretch(1)
        area.setWidget(holder)
        return area

    # ------------------------------------------------------------------- carga
    def load(self, car: CarData | None) -> None:
        self.car = car
        self.car_folder = Path(car.folder) if car is not None else None
        self._loading = True
        try:
            for field in (self.pressure_front, self.pressure_rear, self.brake_bias,
                          self.brake_torque, self.ride_front, self.ride_rear):
                field.blockSignals(True)
            self._fill_identity(car)
            self._load_quick_fields(car)
            self._load_aero(car)
            self._refresh_curve()
            self._refresh_gears()
            self._refresh_diagnostics()
            self._refresh_lists()
            self._refresh_catalog()
            self._refresh_history()
            self._refresh_inspector()
            self.clone_note.setText(
                f"Se clonara una copia completa de {car.folder.name} en content/cars." if car is not None
                else "El clonado necesita un coche cargado."
            )
        finally:
            for field in (self.pressure_front, self.pressure_rear, self.brake_bias,
                          self.brake_torque, self.ride_front, self.ride_rear):
                field.blockSignals(False)
            self._loading = False

    def set_library(self, cars, meta_cache: dict | None = None, favorites=()) -> None:
        """Biblioteca para comparar, clonar y sacar estadisticas globales."""
        self._library = list(cars or [])
        self._meta_cache = dict(meta_cache or {})
        self._favorites = set(favorites or ())
        self._prepare_library_stats()
        self.rival.blockSignals(True)
        current = self.rival.currentText()
        self.rival.clear()
        for car in self._library:
            if self.car is not None and car.name == self.car.name:
                continue
            self.rival.addItem(car.ui_name, car.name)
        if current:
            index = self.rival.findText(current)
            if index >= 0:
                self.rival.setCurrentIndex(index)
        self.rival.blockSignals(False)
        self.clone_button.setEnabled(bool(self.car_folder))
        stats = analysis.library_stats(self._library, self._meta_cache, self._favorites)
        for index, (label, value) in enumerate(stats):
            if index < len(self._stat_keys):
                self.library_stats.set(self._stat_keys[index], value)

    def _prepare_library_stats(self) -> None:
        """Crea las filas de estadisticas una sola vez (los valores se refrescan)."""
        if self._stats_ready:
            return
        labels = analysis.library_stats([], {}, ())
        self._stat_keys = []
        for index, (label, _value) in enumerate(labels):
            key = f"stat{index}"
            self._stat_keys.append(key)
            self.library_stats.add(key, label, "", "info", "Estadisticas de la biblioteca")
        self._stats_ready = True

    def _fill_identity(self, car: CarData | None) -> None:
        estimate = analysis.estimate_performance(car) if car is not None else None
        if estimate is None:
            for key in ("zero100", "zero200", "top", "pw", "accel"):
                self.stats.set(key, "—")
            return
        self.stats.set("zero100", f"{estimate.zero_100:.2f}" if estimate.zero_100 else "> 90")
        self.stats.set("zero200", f"{estimate.zero_200:.2f}" if estimate.zero_200 else "> 90")
        self.stats.set("top", f"{estimate.top_speed_kmh:.0f}")
        self.stats.set("pw", f"{estimate.cv_per_tonne:.0f} CV/t · {estimate.kg_per_cv:.2f} kg/CV")
        self.stats.set("accel", f"{estimate.max_accel_g:.2f}")

    def _quick_key_available(self, car: CarData, filename: str, section: str, key: str) -> bool:
        """Solo se editan claves que el coche ya trae escritas."""
        if not car.has_file(filename) or not section:
            return False
        return car.ini(filename).has(section, key)

    def _load_quick_fields(self, car: CarData | None) -> None:
        if car is None:
            self._quick_keys = {}
            for widget in (self.pressure_front, self.pressure_rear, self.brake_bias,
                           self.brake_torque, self.ride_front, self.ride_rear):
                widget.setEnabled(False)
            return
        front = car.compound_sections(True)
        rear = car.compound_sections(False)
        self._quick_keys = {
            "pressure_front": self._quick_key_available(
                car, "tyres.ini", front[0] if front else "", "PRESSURE_STATIC"),
            "pressure_rear": self._quick_key_available(
                car, "tyres.ini", rear[0] if rear else "", "PRESSURE_STATIC"),
            "brake_bias": self._quick_key_available(car, "brakes.ini", "DATA", "FRONT_SHARE"),
            "brake_torque": self._quick_key_available(car, "brakes.ini", "DATA", "MAX_TORQUE"),
            "ride_front": self._quick_key_available(car, "suspensions.ini", "FRONT", "ROD_LENGTH"),
            "ride_rear": self._quick_key_available(car, "suspensions.ini", "REAR", "ROD_LENGTH"),
        }
        fields = {
            "pressure_front": (self.pressure_front, car.tyre_pressure(True)),
            "pressure_rear": (self.pressure_rear, car.tyre_pressure(False)),
            "brake_bias": (self.brake_bias, car.brake_bias_percent),
            "brake_torque": (self.brake_torque, car.brake_torque),
            "ride_front": (self.ride_front, car.ride_height_offset(True)),
            "ride_rear": (self.ride_rear, car.ride_height_offset(False)),
        }
        for name, (widget, value) in fields.items():
            available = self._quick_keys.get(name, False)
            widget.setEnabled(available)
            widget.setToolTip(
                widget.toolTip() if available else
                "Este coche no declara esta clave; no se inventa."
            )
            if available and value:
                widget.setValue(value)
        missing = [name for name, ok in self._quick_keys.items() if not ok]
        self.quick_note.setText(
            i18n.tr("Este coche no declara: {}.", ", ".join(sorted(missing))) if missing
            else i18n.tr("Todas las claves rapidas existen en este coche.")
        )

    def _load_aero(self, car: CarData | None) -> None:
        self.aero_combo.blockSignals(True)
        self.aero_combo.clear()
        if car is not None:
            for entry in car.advanced_settings():
                if entry.filename.lower() != "aero.ini":
                    continue
                self.aero_combo.addItem(f"{entry.section} · {entry.key}", entry.identity)
        self.aero_combo.blockSignals(False)
        has_aero = self.aero_combo.count() > 0
        self.aero_combo.setEnabled(has_aero)
        self.aero_value.setEnabled(has_aero)
        self.aero_note.setText(
            f"aero.ini detectado con {self.aero_combo.count()} parametros editables."
            if has_aero else
            "Este coche no declara aero.ini: el downforce va dentro del modelo de AC."
        )
        self._sync_aero_value()

    def _refresh_lists(self) -> None:
        self.setup_list.clear()
        self.version_list.clear()
        self.backup_list.clear()
        name = self.car.name if self.car is not None else ""
        if not name:
            self.backup_note.setText("Elige un coche para ver sus respaldos.")
            return
        for info in garage.list_setups(name):
            item = QListWidgetItem(f"{info.name}  ·  {info.subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, info.name)
            self.setup_list.addItem(item)
        for version in garage.list_versions(name):
            item = QListWidgetItem(f"{version.label}  ·  {version.created}")
            item.setData(Qt.ItemDataRole.UserRole, version.version_id)
            self.version_list.addItem(item)
        self._refresh_backups()

    def _refresh_backups(self) -> None:
        self.backup_list.clear()
        if self.car_folder is None:
            self.backup_note.setText("Elige un coche para ver sus respaldos.")
            return
        backups = garage.list_backups(self.car_folder)
        for info in backups:
            item = QListWidgetItem(
                f"{info.name}  ·  {info.created}  ·  {info.size / 1024:.0f} KB"
                f"  ·  {len(info.members)} ficheros"
            )
            item.setData(Qt.ItemDataRole.UserRole, str(info.path))
            self.backup_list.addItem(item)
        self.backup_note.setText(
            f"{len(backups)} respaldo(s) en quickmechanic_backups." if backups
            else "Todavia no hay respaldos: se crean solos antes de cada guardado y swap."
        )

    def _refresh_catalog(self) -> None:
        circuits = garage.setup_circuits(self.car.name) if self.car is not None else []
        existing = {self.setup_circuit.itemText(index) for index in range(self.setup_circuit.count())}
        for name in circuits:
            if name not in existing:
                self.setup_circuit.addItem(name)

    def _refresh_history(self) -> None:
        self.history_view.clear()
        if self.car is None:
            return
        changes = garage.read_history(self.car.name, 60)
        if not changes:
            self.history_view.setHtml(
                f"<p style='color:{theme.MUTED}'>Aun no hay cambios registrados para este coche. "
                "Cada guardado anota lo que ha cambiado y cuanto.</p>"
            )
            return
        rows = "".join(
            f"<tr><td style='color:{theme.MUTED};padding-right:10px'>{html.escape(change.moment)}</td>"
            f"<td>{html.escape(change.area)}</td>"
            f"<td>{html.escape(change.parameter)}</td>"
            f"<td style='color:{theme.INFO}'>{html.escape(change.before)} → "
            f"<b style='color:{theme.ACCENT}'>{html.escape(change.after)}</b></td></tr>"
            for change in changes[:60]
        )
        self.history_view.setHtml(
            f"<html><body style='color:{theme.FG};font-size:12px'>"
            f"<table cellspacing='0'>{rows}</table></body></html>"
        )

    # ------------------------------------------------------------------ curva
    def _refresh_curve(self) -> None:
        car = self.car
        mode = self.curve_mode.currentData() if hasattr(self, "curve_mode") else "torque"
        if car is None:
            self.curve.set_points([])
            self.curve.setEnabled(False)
            self.curve_note.setText("Elige un coche con carpeta data/ para ver su curva.")
            return
        points = car.power_points()
        if mode == "power":
            self.curve.setEnabled(False)
            self.curve.unit = "CV"
            self.curve.set_points([
                (rpm, units.hp_from_torque(nm, rpm)) for rpm, nm in points
            ])
            self.curve_note.setText(
                "Vista de potencia: la curva real que se edita es el par (power.lut). "
                "Cambia a «Par» para arrastrar los puntos."
            )
            return
        if mode == "brake":
            self.curve.setEnabled(False)
            self.curve.unit = "N"
            self.curve.set_points(_brake_curve(car))
            self.curve_note.setText(
                "Fuerza de frenada estimada: el limite lo pone el par de freno (MAX_TORQUE) o el "
                "agarre disponible, y crece con la carga aerodinamica. Se ajusta con el par de "
                "frenado y el reparto de los campos de la izquierda."
            )
            return
        self.curve.setEnabled(True)
        self.curve.unit = "Nm"
        self.curve.set_points(points)
        peak_rpm, peak = car.peak_torque()
        self.curve_note.setText(
            f"{len(points)} puntos de {car.power_curve_file}. Par maximo {peak:.0f} Nm a "
            f"{peak_rpm:.0f} rpm. Arrastra un punto para reescribir esa fila del .lut."
        )

    def _on_curve_point(self, index: int, value: float) -> None:
        if self._loading or self.car is None:
            return
        if self.curve_mode.currentData() != "torque":
            return
        if not self.car.set_power_point(index, value):
            return
        self._fill_identity(self.car)
        self._refresh_gears()
        self.changed.emit()
        self.status.emit(f"Punto {index + 1} de power.lut ajustado a {value:.1f} Nm")

    # -------------------------------------------------------------- simulador
    def _refresh_gears(self) -> None:
        car = self.car
        if car is None:
            self.gear_chart.set_series([])
            self.gear_legend.set_entries([])
            self.gear_note.setText("")
            return
        gears = analysis.gear_speeds(car)
        if not gears:
            self.gear_chart.set_series([])
            self.gear_legend.set_entries([])
            self.gear_note.setText("No hay relaciones de cambio legibles.")
            return
        shift_rpm = analysis.shift_rpm(car)
        idle = float(car.idle_rpm or 900)
        series = []
        for index, gear in enumerate(gears):
            color = curves.PALETTE[index % len(curves.PALETTE)]
            series.append({
                "label": f"{gear.gear}ª",
                "color": color,
                "points": [(gear.power_kmh, idle), (gear.power_kmh, min(shift_rpm, 12000)),
                           (gear.shift_kmh, min(shift_rpm, 12000))],
                "markers": [gear.shift_kmh],
            })
        self.gear_chart.set_series(series)
        self.gear_legend.set_entries([(item["label"], item["color"]) for item in series])
        top = gears[-1].shift_kmh
        self.gear_note.setText(
            f"Cada linea es una marcha: sube de ralenti a {shift_rpm:.0f} rpm y las lineas "
            f"discontinuas marcan el punto de cambio. Ultima marcha a {top:.0f} km/h."
        )

    def _calculate_gearing(self) -> None:
        car = self.car
        if car is None:
            return
        target = float(self.circuit.currentData() or 0.0)
        plan = analysis.optimal_gearing(car, target or None)
        if plan is None:
            self.gearing_note.setText("Este coche no tiene relaciones suficientes para recalcularlas.")
            self.gearing_apply.setEnabled(False)
            return
        self._gearing_plan = plan
        self.gearing_apply.setEnabled(True)
        ratios = " · ".join(f"{ratio:.3f}" for ratio in plan.ratios)
        notes = " ".join(plan.notes)
        self.gearing_note.setText(f"Propuesta: {ratios}. {notes}")
        self.status.emit("Relaciones propuestas; revisa el simulador antes de aplicarlas.")

    def _apply_gearing(self) -> None:
        plan = getattr(self, "_gearing_plan", None)
        if plan is None or self.car is None:
            return
        applied = analysis.apply_gearing(self.car, plan)
        self._refresh_gears()
        self._refresh_diagnostics()
        self.changed.emit()
        self.status.emit(f"{applied} relaciones escritas en drivetrain.ini (sin guardar todavia)")

    # ------------------------------------------------------------- diagnostico
    def _refresh_diagnostics(self) -> None:
        car = self.car
        self.diagnostic_view.clear()
        if car is None:
            return
        estimate = analysis.estimate_performance(car)
        findings = analysis.diagnostics(car, estimate)
        ok, warn, error = analysis.severity_counts(findings)
        rows = "".join(
            f"<li style='margin:2px 0'>{finding.icon} <b>{html.escape(finding.area)}</b> · "
            f"{html.escape(finding.message)}</li>"
            for finding in findings
        )
        self.diagnostic_view.setHtml(
            f"<html><body style='color:{theme.FG};font-size:12px'>"
            f"<p><b>🟢 {ok}</b> correctos · <b>🟡 {warn}</b> avisos · <b>🔴 {error}</b> errores</p>"
            f"<ul style='margin:0;padding-left:16px'>{rows}</ul></body></html>"
        )
        if estimate is not None and estimate.assumptions:
            self.diagnostic_view.append(
                f"<p style='color:{theme.MUTED}'>Supuestos: {' · '.join(estimate.assumptions)}</p>"
            )

    # ---------------------------------------------------------------- comparar
    def _compare(self) -> None:
        if self.car is None:
            return
        name = self.rival.currentData()
        rival = next((car for car in self._library if car.name == name), None)
        if rival is None or self.car.folder == rival.folder:
            self.compare_view.setHtml(
                f"<p style='color:{theme.MUTED}'>Elige otro coche de la lista para compararlo.</p>"
            )
            return
        other = CarData.from_car(rival)
        if not other.editable:
            self.compare_view.setHtml(
                f"<p style='color:{theme.MUTED}'>'{rival.ui_name}' solo tiene data.acd: "
                "extraelo con Content Manager para poder compararlo.</p>"
            )
            return
        rows = analysis.compare_cars([self.car, other])
        body = "".join(
            f"<tr><td style='color:{theme.MUTED};padding:2px 12px 2px 0'>{html.escape(label)}</td>"
            f"<td><b>{html.escape(values[0])}</b></td>"
            f"<td>{html.escape(values[1])}</td></tr>"
            for label, values in rows
        )
        self.compare_view.setHtml(
            f"<html><body style='color:{theme.FG};font-size:12px'>"
            f"<p><b style='color:{theme.ACCENT}'>{html.escape(self.car.ui_name)}</b> frente a "
            f"<b>{html.escape(other.ui_name)}</b></p>"
            f"<table cellspacing='0'>{body}</table></body></html>"
        )

    # ----------------------------------------------------------------- presets
    def _apply_style(self, style: str) -> None:
        if self.car is None:
            return
        result = analysis.apply_style(self.car, style)
        detalle = (
            i18n.tr("Aplicado: {}", ", ".join(result.applied)) if result.applied else i18n.tr("Sin cambios")
        )
        if result.notes:
            detalle += "  ·  " + " ".join(result.notes)
        self.style_note.setText(detalle)
        if result.applied:
            self._after_change()

    def _after_change(self) -> None:
        """Refresca la pestana tras tocar el coche en memoria."""
        self.load(self.car)
        self.changed.emit()

    # ------------------------------------------------------------ ajustes varios
    def _store_quick(self, _value: float = 0.0) -> None:
        car = self.car
        if self._loading or car is None:
            return
        applied: list[str] = []
        try:
            if self._quick_keys.get("pressure_front"):
                car.set_tyre_pressure(True, self.pressure_front.value())
                applied.append("presion delantera")
            if self._quick_keys.get("pressure_rear"):
                car.set_tyre_pressure(False, self.pressure_rear.value())
                applied.append("presion trasera")
            if self._quick_keys.get("brake_bias"):
                car.brake_bias_percent = self.brake_bias.value()
                applied.append("reparto de freno")
            if self._quick_keys.get("brake_torque"):
                car.brake_torque = self.brake_torque.value()
                applied.append("par de frenado")
            if self._quick_keys.get("ride_front"):
                car.set_ride_height_offset(True, self.ride_front.value())
                applied.append("altura delantera")
            if self._quick_keys.get("ride_rear"):
                car.set_ride_height_offset(False, self.ride_rear.value())
                applied.append("altura trasera")
        except (ValueError, OSError) as error:
            self.status.emit(f"No se pudo aplicar: {error}")
            return
        if not applied:
            self.status.emit(i18n.tr("Este coche no declara ninguna de esas claves; no se ha tocado nada."))
            return
        self._refresh_diagnostics()
        self.changed.emit()
        self.status.emit(i18n.tr("Ajustado: {}", ", ".join(applied)))

    # -------------------------------------------------------- inspector .ini
    def _queue_inspector(self, _text: str = "") -> None:
        self._inspector_timer.start()

    def _refresh_inspector(self) -> None:
        car = self.car
        self.inspector_view.clear()
        if car is None:
            return
        needle = self.inspector_filter.text().strip().casefold()
        rows: list[tuple[str, str, str, str]] = []
        for filename in self.INSPECTOR_FILES:
            if not car.has_file(filename):
                continue
            ini = car.ini(filename)
            for section in ini.sections():
                for key in ini.keys(section):
                    rows.append((filename, section, key, ini.get(section, key)))
        if needle:
            rows = [
                row for row in rows
                if any(needle in field.casefold() for field in row)
            ]
        limit = 600
        shown = rows[:limit]
        body = "".join(
            f"<tr><td style='color:{theme.MUTED}'>{html.escape(filename)}</td>"
            f"<td>{html.escape(section)}</td>"
            f"<td style='color:{theme.ACCENT}'>{html.escape(key)}</td>"
            f"<td>{html.escape(value)}</td></tr>"
            for filename, section, key, value in shown
        )
        aviso = (
            f"<p style='color:{theme.MUTED}'>{len(rows)} coincidencias; se muestran {len(shown)}.</p>"
            if len(rows) > limit else f"<p style='color:{theme.MUTED}'>{len(rows)} claves.</p>"
        )
        self.inspector_view.setHtml(
            f"<html><body style='color:{theme.FG};font-size:12px'>{aviso}"
            f"<table cellspacing='0' cellpadding='2'>{body}</table></body></html>"
        )

    # -------------------------------------------------------------- clonado
    def _clone_car(self) -> None:
        if self.car_folder is None or not self.car_folder.is_dir():
            QMessageBox.information(self, "Sin coche", "Elige un coche de la biblioteca para clonarlo.")
            return
        cars_root = self.car_folder.parent
        if not cars_root.is_dir():
            QMessageBox.warning(self, "Ruta no valida", "No se encontro la carpeta content/cars del coche.")
            return
        try:
            suggested = garage.suggest_clone_name(self.car_folder, cars_root)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se puede clonar", str(error))
            return
        name, accepted = QInputDialog.getText(
            self, "Clonar coche", "Nombre de la carpeta nueva:", text=self.clone_name.text().strip() or suggested
        )
        if not accepted:
            return
        name = name.strip() or suggested
        destination = cars_root / name
        if destination.exists():
            QMessageBox.warning(self, "Ya existe", f"En content/cars ya hay una carpeta llamada {name}.")
            return
        megabytes = _folder_size_mb(self.car_folder)
        if QMessageBox.question(
            self, "Confirmar clonado",
            f"Se copiara '{self.car_folder.name}' completo ({megabytes:.0f} MB) a '{name}'.\n"
            "El coche original no se modifica. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            result = garage.clone_car(self.car_folder, cars_root, name)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo clonar", str(error))
            return
        self.clone_name.clear()
        self.clone_note.setText(
            f"Clon creado en {result.folder.name} con {result.files} ficheros. " + " ".join(result.notes)
        )
        self.status.emit(f"Coche clonado: {result.name}")
        self.libraryChanged.emit()

    def _sync_aero_value(self) -> None:
        identity = self.aero_combo.currentData()
        if not identity or self.car is None:
            return
        for entry in self.car.advanced_settings():
            if entry.identity == identity:
                self.aero_value.setValue(entry.value)
                return

    def _store_aero(self) -> None:
        identity = self.aero_combo.currentData()
        if not identity or self.car is None:
            return
        filename, section, key = identity
        if self.car.set_advanced_value(filename, section, key, self.aero_value.value()):
            self.status.emit(f"{key} de {filename} ajustado a {self.aero_value.value()}")
            self.changed.emit()
        else:
            self.status.emit(f"No se pudo escribir {key} en {filename}")

    # ----------------------------------------------------------- setup manager
    def _save_setup(self) -> None:
        car = self.car
        if car is None:
            return
        name = self.setup_name.text().strip()
        if not name:
            QMessageBox.information(self, "Falta el nombre", "Escribe un nombre para el setup.")
            return
        try:
            path = garage.save_setup(
                car.name, name, car.setup_snapshot(),
                circuit=self.setup_circuit.currentText().strip(),
                conditions=self.setup_conditions.text().strip(),
                style=self.setup_style.currentData() or "",
            )
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo guardar", str(error))
            return
        self._refresh_lists()
        self._refresh_catalog()
        self.status.emit(f"Setup guardado en {path}")

    def _load_setup(self) -> None:
        item = self.setup_list.currentItem()
        if item is None or self.car is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        try:
            snapshot = garage.load_setup(self.car.name, name)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo cargar", str(error))
            return
        self._restore_snapshot(snapshot, f"Setup '{name}' cargado en memoria")

    def _delete_setup(self) -> None:
        item = self.setup_list.currentItem()
        if item is None or self.car is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if garage.delete_setup(self.car.name, name):
            self._refresh_lists()
            self.status.emit(f"Setup '{name}' borrado")

    def _export_setup(self) -> None:
        item = self.setup_list.currentItem()
        if item is None or self.car is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        path, _filter = QFileDialog.getSaveFileName(
            self, "Exportar setup", f"{name}.qmsetup", "Setup de Quick Mechanic (*.qmsetup)"
        )
        if not path:
            return
        try:
            target = garage.export_setup(self.car.name, name, path)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo exportar", str(error))
            return
        self.status.emit(f"Setup exportado a {target}")

    def _import_setup(self) -> None:
        if self.car is None:
            return
        path, _filter = QFileDialog.getOpenFileName(
            self, "Importar setup", "", "Setup de Quick Mechanic (*.qmsetup)"
        )
        if not path:
            return
        try:
            name, snapshot = garage.import_setup(path)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo importar", str(error))
            return
        self._restore_snapshot(snapshot, f"Setup importado '{name}' aplicado en memoria")

    # -------------------------------------------------------------- versiones
    def _save_version(self) -> None:
        if self.car is None:
            return
        label = self.version_label.text().strip() or "version"
        try:
            path = garage.save_version(self.car.name, label, self.car.setup_snapshot())
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo guardar la version", str(error))
            return
        self._refresh_lists()
        self.status.emit(f"Version guardada en {path}")

    def _restore_version(self) -> None:
        item = self.version_list.currentItem()
        if item is None or self.car is None:
            return
        version_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            snapshot = garage.load_version(self.car.name, version_id)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo restaurar", str(error))
            return
        self._restore_snapshot(snapshot, f"Version {version_id} restaurada en memoria")

    def _delete_version(self) -> None:
        item = self.version_list.currentItem()
        if item is None or self.car is None:
            return
        version_id = item.data(Qt.ItemDataRole.UserRole)
        if garage.delete_version(self.car.name, version_id):
            self._refresh_lists()
            self.status.emit(f"Version {version_id} borrada")

    def _restore_snapshot(self, snapshot: dict, message: str) -> None:
        if self.car is None:
            return
        try:
            self.car.restore_setup(snapshot)
        except ValueError as error:
            QMessageBox.warning(self, "Setup no compatible", str(error))
            return
        self.carReloaded.emit()
        self.status.emit(f"{message}. Guarda para escribirlo en el coche.")

    # -------------------------------------------------------------- respaldos
    def _create_backup(self) -> None:
        if self.car_folder is None:
            return
        from .. import swaps

        try:
            archive = swaps.create_backup(self.car_folder)
        except swaps.SwapError as error:
            QMessageBox.warning(self, "No se pudo respaldar", str(error))
            return
        self._refresh_backups()
        self.status.emit(f"Respaldo creado: {archive.name}")

    def _restore_member(self) -> None:
        item = self.backup_list.currentItem()
        if item is None or self.car_folder is None:
            return
        archive = Path(item.data(Qt.ItemDataRole.UserRole))
        members = [name for name in garage.backup_members(archive) if name.startswith("data") or name == "data.acd"]
        if not members:
            QMessageBox.information(self, "Respaldo vacio", "Este respaldo no contiene archivos de data/.")
            return
        choice, accepted = QInputDialog.getItem(
            self, "Restaurar un fichero", "Ficheros del respaldo:", members, 0, False
        )
        if not accepted or not choice:
            return
        try:
            path = garage.restore_member(archive, choice, self.car_folder)
        except garage.GarageError as error:
            QMessageBox.warning(self, "No se pudo restaurar", str(error))
            return
        self.carReloaded.emit()
        self.status.emit(f"Restaurado {path.name} desde {archive.name} (con respaldo previo)")

    def _prune_backups(self) -> None:
        if self.car_folder is None:
            return
        removed = garage.prune_backups(self.car_folder, 5)
        self._refresh_backups()
        self.status.emit(f"{removed} respaldo(s) antiguos borrados; se conservan los 5 ultimos")

    # ---------------------------------------------------------------- informes
    def _export_report(self, fmt: str) -> None:
        if self.car is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Guardar informe", f"{self.car.name}_informe.{fmt}",
            "Texto (*.txt)" if fmt == "txt" else "HTML (*.html)",
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != f".{fmt}":
            target = target.with_suffix(f".{fmt}")
        try:
            target.write_text(
                analysis.report(self.car, analysis.estimate_performance(self.car), fmt=fmt),
                encoding="utf-8",
            )
        except OSError as error:
            QMessageBox.warning(self, "No se pudo escribir el informe", str(error))
            return
        self.status.emit(f"Informe guardado en {target}")


def _grid_holder(grid: QGridLayout) -> QWidget:
    holder = QWidget()
    holder.setLayout(grid)
    return holder


def _heading(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionLabel")
    return label


def _folder_size_mb(folder: Path) -> float:
    """Tamano aproximado de la carpeta del coche, para avisar antes de clonar."""
    total = 0
    try:
        for path in Path(folder).rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
    except OSError:
        return 0.0
    return total / (1024 * 1024)


def _brake_curve(car: CarData) -> list[tuple[float, float]]:
    """Fuerza de frenada disponible (N) segun la velocidad.

    Se queda con el menor de los dos limites: lo que puede frenar el sistema
    (MAX_TORQUE de brakes.ini entre el radio de rueda) o lo que aguanta el
    neumatico, que gana agarre con la carga aerodinamica.
    """
    radius = car.driven_wheel_radius() or 0.33
    brake_force = (car.brake_torque or 0.0) / radius
    mass = car.mass or 1200.0
    cda = analysis.aero_cda(car)
    out = []
    for speed in range(0, 281, 20):
        v = speed / 3.6
        downforce = 0.5 * analysis.RHO * cda * v * v
        grip = analysis.DEFAULT_TYRE_MU * (mass * analysis.GRAVITY + downforce * 2.0)
        limit = min(brake_force, grip) if brake_force else grip
        out.append((float(speed), limit))
    return out
