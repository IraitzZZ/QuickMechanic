"""Quick Mechanic — editor de coches de Assetto Corsa.

Uso::

    python -m quickmechanic                    abre la ventana
    python -m quickmechanic --selftest         comprueba la instalacion de AC

La ventana esta pensada como el panel de un box: arriba la cabecera con el
nombre de la app y los accesos (recargar, abrir una carpeta data, elegir la
instalacion de AC); a la izquierda la ficha del coche con su previsualizacion
(la imagen ``preview`` de la skin) y la lista de coches; en el centro la
cabecera del coche elegido con sus datos clave y las pestanas de edicion; y
abajo, siempre visible, el guardado.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QCloseEvent, QDesktopServices, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QListWidgetItem,
    QSplitter,
    QSystemTrayIcon,
    QTextBrowser,
    QVBoxLayout,
)

from .qt_i18n import QAction, QDialog, QFileDialog, QFrame, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QTabWidget, QWidget

from . import (
    APP_NAME,
    __version__,
    ac_scanner,
    car_data,
    car_repair,
    content_manager,
    drift,
    tracks,
    garage,
    i18n,
    license as app_license,
    presets,
    settings,
    skins,
    swaps,
    theme,
    widgets,
)
from .branding import LoadingSplash, app_icon
from .cm_panel import ContentManagerPanel
from .command_palette import Command, CommandPalette
from .access_gate import AccessGate, AccessMonitor
from .discord_link import Access, Status
from .guide import DISCORD_URL, QuickGuideDialog
from .track_tab import TrackTab
from .tabs import AidsTab, AdvancedTab, ChassisTab, DashboardTab, GearboxTab, InfoTab, LabTab, MotorTab
from .tabs.upgrade_tab import UpgradeTab
from . import acd

SIDEBAR_MIN_WIDTH = 270
SIDEBAR_MAX_WIDTH = 400


def _tab_page(content: QWidget) -> QScrollArea:
    """Envuelve una pestaña en un area con desplazamiento.

    Sin esto, el ancho minimo de cada pestaña (tablas y columnas fijas) se propaga
    a la ventana y el contenido se superpone en ventanas estrechas (1200 px).
    Ahora la pestaña se encoge y aparece una barra horizontal si hace falta.
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(content)
    return area
class _LibraryScanWorker(QObject):
    """Escanea disco fuera del hilo de la interfaz y precarga metadatos."""

    completed = pyqtSignal(object, object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, ac_root: Path | None) -> None:
        super().__init__()
        self.ac_root = ac_root

    @pyqtSlot()
    def run(self) -> None:
        try:
            cars = ac_scanner.list_cars(self.ac_root) if self.ac_root else []
            metadata = {}
            total = len(cars)
            for index, car in enumerate(cars, 1):
                try:
                    metadata[car.folder] = skins.read_car_meta(car.folder)
                except (OSError, ValueError, TypeError):
                    pass
                self.progress.emit(index, total)
            self.completed.emit(cars, metadata)
        except Exception as error:
            self.failed.emit(str(error))


class _CarLoadWorker(QObject):
    """Desempaqueta data.acd y lee la fisica del coche fuera del hilo de la interfaz."""

    completed = pyqtSignal(int, object, object, object, str)  # token, origen, coche, datos, mensaje
    failed = pyqtSignal(int, object, str)

    def __init__(self, token: int, source: ac_scanner.Car) -> None:
        super().__init__()
        self.token = token
        self.source = source

    @pyqtSlot()
    def run(self) -> None:
        try:
            car = self.source
            message = ""
            car_dir = Path(self.source.folder)
            if acd.needs_unpack(car_dir):
                ok, message = acd.unpack(car_dir)
                if ok:
                    car = ac_scanner.Car.from_data_dir(car_dir / "data")
            data = car_data.CarData.from_car(car) if car.editable else None
            self.completed.emit(self.token, self.source, car, data, message)
        except Exception as error:  # noqa: BLE001 - el fallo se muestra sin cerrar la aplicacion
            self.failed.emit(self.token, self.source, str(error))


class MainWindow(QMainWindow):
    RECENT_LIMIT = 8  # coches recientes que se recuerdan para Ctrl+Shift+H
    RECENT_TOOL_LIMIT = 5  # herramientas recientes que se muestran en la pantalla de inicio
    TAB_TITLES = ("Resumen", "Motor", "Caja de cambios", "Chasis", "Diagnóstico", "Asistencias", "Avanzado", "Taller", "Circuitos", "Mejoras")
    SORT_MODES = ("name", "favorites", "editable", "recent")  # orden de la lista, Ctrl+Shift+K
    SORT_LABELS = {
        "name": "nombre",
        "favorites": "favoritos primero",
        "editable": "editables primero",
        "recent": "recientes primero",
    }

    def __init__(
        self,
        ac_root: str | Path | None = None,
        extra_cars: list[ac_scanner.Car] | None = None,
        background: bool = False,
        access_monitor: AccessMonitor | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  ·  VEHICLE ENGINEERING")
        self.setWindowIcon(app_icon())
        self.resize(1760, 1000)
        self.setMinimumSize(1180, 740)
        self._animations: list[QPropertyAnimation] = []
        self._background_start = background
        self._tray: QSystemTrayIcon | None = None
        self._close_to_tray = bool(settings.get("close_to_tray", sys.platform == "win32"))
        self._exit_requested = False
        self._access_monitor = access_monitor
        self._locked = False
        self._relocking = False
        self._scan_thread: QThread | None = None
        self._scan_worker: _LibraryScanWorker | None = None
        self._load_thread: QThread | None = None
        self._load_worker: _CarLoadWorker | None = None
        self._car_request = 0  # cada seleccion de coche lo incrementa; resultados viejos se descartan
        self._tracks: list[tracks.TrackInfo] = []
        self._track_scan_error = ""
        self._show_guide_on_start = bool(settings.get("show_guide", True)) and not background
        self._show_splash_on_start = bool(settings.get("show_loading_splash", True)) and not background

        self._extra_cars: list[ac_scanner.Car] = list(extra_cars or [])
        self._cars: list[ac_scanner.Car] = []
        self._shown: list[ac_scanner.Car] = []
        self._search_terms: dict[Path, str] = {}
        self._meta_cache: dict[Path, skins.CarMeta] = {}
        self._car: car_data.CarData | None = None
        self._source: ac_scanner.Car | None = None
        self._skin_choices: dict[str, str] = self._load_skin_choices()
        saved_favorites = settings.get("favorites", []) or []
        self._favorites = set(saved_favorites) if isinstance(saved_favorites, (list, tuple, set)) else set()
        saved_recent = settings.get("recent_cars", []) or []
        self._recent_cars: list[str] = (
            [folder for folder in saved_recent if isinstance(folder, str)][: self.RECENT_LIMIT]
            if isinstance(saved_recent, list) else []
        )
        self._recent_menu: QMenu | None = None
        saved_tools = settings.get("recent_tools", []) or []
        self._recent_tools: list[int] = (
            [index for index in saved_tools if isinstance(index, int) and 0 < index < len(self.TAB_TITLES)][: self.RECENT_TOOL_LIMIT]
            if isinstance(saved_tools, list) else []
        )
        saved_sort = settings.get("sort_mode", "name")
        self._sort_mode = saved_sort if saved_sort in self.SORT_MODES else "name"
        self._visible_car_keys: list[tuple[str, Path]] = []
        self._history: list[dict] = []
        self._history_index = -1
        self._history_applying = False
        self.ac_root: Path | None = self._resolve_ac_root(ac_root)
        configured_cm = settings.get("content_manager_path", str(content_manager.DEFAULT_PATH))
        self.content_manager_path = content_manager.find_executable(configured_cm)

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_filter)

        self._splash = LoadingSplash() if self._show_splash_on_start else None
        self._splash_finish_pending = False
        if self._splash is not None:
            self._splash.fadeFinished.connect(self._complete_splash_finish)
            self._splash.show()
            QApplication.processEvents()
        self._build_ui()
        self._build_actions()
        if self._access_monitor is not None:
            self._build_account_bar()
        self._restore_window_state()
        self._restore_last_tab()
        self._restore_filters()
        if self._splash is not None:
            self._splash.set_status("ESCANEANDO BIBLIOTECA DE COCHES", 20)
            QApplication.processEvents()
        if sys.platform == "win32" or self._close_to_tray or self._background_start:
            self._setup_tray()
        self._reload_cars()

    # ------------------------------------------------------------------- setup
    @staticmethod
    def _resolve_ac_root(ac_root: str | Path | None) -> Path | None:
        if ac_root:
            candidate = Path(ac_root)
            if (candidate / "content" / "cars").is_dir():
                return candidate
        stored = settings.get("ac_root")
        if stored and (Path(stored) / "content" / "cars").is_dir():
            return Path(stored)
        return ac_scanner.find_ac_root()

    @staticmethod
    def _load_skin_choices() -> dict[str, str]:
        stored = settings.get("skin_choices")
        if isinstance(stored, dict):
            return {str(key): str(value) for key, value in stored.items()}
        return {}

    # ------------------------------------------------------------------- interfaz
    # ------------------------------------------------------------- cuenta Discord
    def _build_account_bar(self) -> None:
        monitor = self._access_monitor
        assert monitor is not None
        bar = self.statusBar()
        self._account_label = QLabel()
        self._account_label.setObjectName("guideProgress")
        bar.addPermanentWidget(self._account_label)
        recheck = QPushButton("Volver a comprobar")
        recheck.setObjectName("ghost")
        recheck.setToolTip("Comprueba ahora mismo tu membresía en el servidor de Discord")
        recheck.clicked.connect(monitor.check_now)
        bar.addPermanentWidget(recheck)
        signout = QPushButton("Cerrar sesión")
        signout.setObjectName("ghost")
        signout.clicked.connect(monitor.sign_out)
        bar.addPermanentWidget(signout)
        monitor.changed.connect(self._on_access_changed)
        self._on_access_changed(monitor.access)

    def _on_access_changed(self, access: Access) -> None:
        if access.granted:
            verified = datetime.fromtimestamp(access.verified_at / 1000).strftime("%d/%m/%Y %H:%M")
            self._account_label.setText(f"● Discord · {access.name or 'miembro'} · MIEMBRO VERIFICADO · {verified}")
            self._set_locked(False)
        elif access.status is Status.UNAVAILABLE and not self._locked:
            self._account_label.setText("◐ Discord no disponible · se volverá a comprobar")
        else:
            self._account_label.setText("○ Acceso no verificado")
            self._lock(access)

    def _set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.setEnabled(not locked)

    def _lock(self, access: Access) -> None:
        """Bloquea la ventana y exige de nuevo la comprobación con Discord."""
        if self._relocking or self._access_monitor is None:
            return
        self._relocking = True
        self._set_locked(True)
        try:
            granted = AccessGate(self._access_monitor).run(access)
        finally:
            self._relocking = False
        if not granted:
            QApplication.quit()

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())
        self.community_notification = self._build_community_notification()
        outer.addWidget(self.community_notification, 0)
        self._community_notification_timer = QTimer(self)
        self._community_notification_timer.setSingleShot(True)
        self._community_notification_timer.timeout.connect(self._hide_discord_notification)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 8)
        body_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        # ------------------------------------------------------------ barra lateral
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.preview = widgets.CarPreview()
        self.preview.setMinimumHeight(300)
        self.preview.skinChanged.connect(self._remember_skin)
        self.preview.setMinimumHeight(250)
        left_layout.addWidget(self.preview, 4)

        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar coche por nombre, carpeta o marca...")

        search_layout.addWidget(self.search, 1)
        self.favorite_filter = QPushButton("★")
        self.favorite_filter.setCheckable(True)
        self.favorite_filter.setObjectName("iconButton")
        self.favorite_filter.setToolTip("Mostrar solo favoritos")
        self.favorite_filter.toggled.connect(self._apply_filter)
        search_layout.addWidget(self.favorite_filter, 0)
        self.editable_filter = QPushButton("Data")
        self.editable_filter.setCheckable(True)
        self.editable_filter.setObjectName("iconButton")
        self.editable_filter.setToolTip("Mostrar solo coches con carpeta data/ editable")
        self.editable_filter.toggled.connect(self._apply_filter)
        search_layout.addWidget(self.editable_filter, 0)
        left_layout.addWidget(search_row, 0)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _text: self._filter_timer.start())
        self.car_list = QListWidget()
        self.car_list.setAlternatingRowColors(False)
        self.car_list.setUniformItemSizes(True)
        self.car_list.currentRowChanged.connect(self._on_car_selected)
        self.car_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.car_list.customContextMenuRequested.connect(self._car_list_menu)
        self.car_list.itemDoubleClicked.connect(lambda _item: self._toggle_favorite())
        # Enter en el buscador pasa el foco a la lista, para elegir con las flechas.
        self.search.returnPressed.connect(self.car_list.setFocus)
        left_layout.addWidget(self.car_list, 5)

        library_heading_row = QHBoxLayout()
        library_heading = QLabel("COLECCIÓN DE VEHÍCULOS")
        library_heading.setObjectName("sectionLabel")
        library_heading_row.addWidget(library_heading, 1)
        self.export_library_button = QPushButton("CSV")
        self.export_library_button.setObjectName("ghost")
        self.export_library_button.setToolTip("Exportar la biblioteca visible a una hoja de cálculo CSV (Ctrl+E)")
        self.export_library_button.clicked.connect(self._export_library_csv)
        library_heading_row.addWidget(self.export_library_button)
        left_layout.addLayout(library_heading_row)
        self.list_status = QLabel("")
        self.list_status.setObjectName("previewSubtitle")
        left_layout.addWidget(self.list_status, 0)

        left.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        left.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        splitter.addWidget(left)

        # -------------------------------------------------------------- zona derecha
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.help_strip = self._build_guide_strip()
        right_layout.addWidget(self.help_strip, 0)
        right_layout.addWidget(self._build_car_header())

        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        right_layout.addWidget(self.banner, 0)

        self.cm_panel = ContentManagerPanel(self.content_manager_path)
        self.cm_panel.syncRequested.connect(self._sync_library)
        self.cm_panel.pathChanged.connect(self._set_content_manager_path)
        right_layout.addWidget(self.cm_panel, 0)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(10)
        self.tabs = QTabWidget()
        self.dashboard_tab = DashboardTab()
        self.motor_tab = MotorTab()
        self.gear_tab = GearboxTab()
        self.chassis_tab = ChassisTab()
        self.info_tab = InfoTab()
        self.info_tab.repair_requested.connect(self._run_car_repair)
        self.aids_tab = AidsTab()
        self.advanced_tab = AdvancedTab()
        self.lab_tab = LabTab()
        self.upgrade_tab = UpgradeTab(lambda: bool(getattr(self, "_car", None) and self._car.changed))
        self.track_tab = TrackTab()
        self.track_tab.openRequested.connect(self._open_track_folder)
        self.track_tab.openIniRequested.connect(self._open_track_ini)
        self.track_tab.statusMessage.connect(self._track_status)
        self.track_tab.trackRefreshRequested.connect(self._refresh_tracks)
        self.upgrade_tab.carChanged.connect(self._reload_current)
        self.upgrade_tab.statusMessage.connect(lambda message: self.footer_status.setText(message))
        self.tabs.addTab(_tab_page(self.dashboard_tab), "Resumen")
        self.dashboard_tab.carRequested.connect(self._open_car_by_folder)
        self.dashboard_tab.toolRequested.connect(self.tabs.setCurrentIndex)
        self.dashboard_tab.searchRequested.connect(self._open_command_palette)
        self.dashboard_tab.actionRequested.connect(self._home_action)
        self.tabs.addTab(_tab_page(self.motor_tab), "Motor")
        self.tabs.addTab(_tab_page(self.gear_tab), "Caja de cambios")
        self.tabs.addTab(_tab_page(self.chassis_tab), "Chasis")
        self.tabs.addTab(_tab_page(self.info_tab), "Diagnostico")
        self.tabs.addTab(_tab_page(self.aids_tab), "Asistencias")
        self.tabs.addTab(_tab_page(self.advanced_tab), "Avanzado")
        self.tabs.addTab(_tab_page(self.lab_tab), "Taller")
        self.tabs.addTab(_tab_page(self.track_tab), "Circuitos")
        self.tabs.addTab(_tab_page(self.upgrade_tab), "Mejoras")
        for index, tip in enumerate((
            "Resumen de rendimiento y estadisticas de la biblioteca",
            "Curvas de potencia y par, limitador y turbo",
            "Editor de relaciones, diferencial y velocidades",
            "Suspension, geometria, frenos y neumaticos",
            "Ficha tecnica, estado de archivos y diagnostico",
            "Compatibilidad y controles de ABS y traccion",
            "Editor experto de parametros numericos existentes en archivos locales",
            "Prestaciones, comparador, gearing, setups, versiones, respaldos e informes",
            "Explora circuitos y layouts instalados; inspección local de solo lectura",
            "Stage tuning, RTO, ficha ui_car, biblioteca de componentes y copias de seguridad",
        )):
            hint = f"  (Ctrl+{index + 1})" if index < 9 else ""
            self.tabs.setTabToolTip(index, tip + hint)
        self.tabs.tabBar().hide()
        self.page_eyebrow = QLabel("GARAJE  ›  RESUMEN")
        self.page_eyebrow.setObjectName("pageEyebrow")
        self.page_title = QLabel("Resumen")
        self.page_title.setObjectName("pageTitle")
        self.page_description = QLabel("Estado de la colección y cálculos derivados de los archivos del coche.")
        self.page_description.setWordWrap(True)
        self.page_description.setObjectName("pageDescription")
        self.page_heading = QWidget()
        self.page_heading.setObjectName("pageHeading")
        page_header_layout = QVBoxLayout(self.page_heading)
        page_header_layout.setContentsMargins(2, 2, 2, 4)
        page_header_layout.setSpacing(2)
        page_header_layout.addWidget(self.page_eyebrow)
        page_header_layout.addWidget(self.page_title)
        page_header_layout.addWidget(self.page_description)

        nav = QFrame()
        nav.setObjectName("navRail")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(10, 8, 10, 12)
        nav_layout.setSpacing(4)
        brand = QLabel("QUICK MECHANIC")
        brand.setObjectName("navBrand")
        nav_layout.addWidget(brand)
        brand_sub = QLabel("Taller de ajuste para Assetto Corsa")
        brand_sub.setObjectName("navBrandSub")
        brand_sub.setWordWrap(True)
        nav_layout.addWidget(brand_sub)
        self.nav_car_status = QLabel("")
        self.nav_car_status.setObjectName("navCarStatus")
        self.nav_car_status.setWordWrap(True)
        nav_layout.addWidget(self.nav_car_status)
        self._update_nav_status(None)
        search_button = QPushButton("⌕    Buscar herramienta")
        search_button.setObjectName("ghost")
        search_button.setToolTip("Buscar una herramienta o acción (Ctrl+K)")
        search_button.clicked.connect(lambda _checked=False: self._open_command_palette())
        nav_layout.addWidget(search_button)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        nav_sections = (
            ("GARAJE", ((0, "◈", "Resumen"),)),
            ("INGENIERÍA", ((1, "⌁", "Motor"), (2, "⚙", "Caja de cambios"), (3, "◉", "Chasis"),
                            (5, "◌", "Asistencias"), (6, "≋", "Avanzado"))),
            ("DIAGNÓSTICO", ((4, "ⓘ", "Diagnóstico"),)),
            ("HERRAMIENTAS", ((7, "⚗", "Taller"), (8, "▦", "Circuitos"), (9, "✎", "Mejoras"))),
        )
        for section_title, items in nav_sections:
            section_label = QLabel(section_title)
            section_label.setObjectName("navSection")
            nav_layout.addWidget(section_label)
            for index, icon, label in items:
                button = QPushButton(f"{icon}    {label}")
                button.setObjectName("navButton")
                button.setCheckable(True)
                button.setToolTip(self.tabs.tabToolTip(index))
                button.clicked.connect(lambda _checked=False, page=index: self.tabs.setCurrentIndex(page))
                self.nav_group.addButton(button, index)
                nav_layout.addWidget(button)
                self.nav_buttons.append(button)
        nav_layout.addStretch(1)
        # El rail puede desplazarse en pantallas bajas: nunca se solapan botones.
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setFixedWidth(196)
        nav_scroll.setWidget(nav)
        self.tabs.currentChanged.connect(self._sync_nav_selection)
        self.nav_group.button(0).setChecked(True)

        self.nav_group.buttonClicked.connect(lambda _button: self._nav_transition())
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab, self.lab_tab):
            tab.changed.connect(self._on_editor_changed)
        self.lab_tab.carReloaded.connect(self._reload_all_views)
        self.lab_tab.libraryChanged.connect(self._reload_cars)
        self.lab_tab.status.connect(lambda message: self.footer_status.setText(message))
        workspace_layout.addWidget(nav_scroll, 0)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        content_layout.addWidget(self.page_heading, 0)
        content_layout.addWidget(self.tabs, 1)
        workspace_layout.addWidget(content, 1)
        right_layout.addWidget(workspace, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        saved_sizes = settings.get("splitter_sizes", [330, 1000])
        splitter.setSizes(saved_sizes if isinstance(saved_sizes, list) and len(saved_sizes) == 2 else [300, 1000])
        self._splitter = splitter
        body_layout.addWidget(splitter, 1)
        outer.addWidget(body, 1)

        outer.addWidget(self._build_footer())

        self.setCentralWidget(central)

    def _build_actions(self) -> None:
        self.undo_action = QAction("Deshacer", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._undo)
        self.addAction(self.undo_action)
        self.redo_action = QAction("Rehacer", self)
        self.redo_action.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Y")])
        self.redo_action.triggered.connect(self._redo)
        self.addAction(self.redo_action)
        self.favorite_action = QAction("Alternar favorito", self)
        self.favorite_action.setShortcut(QKeySequence("Ctrl+D"))
        self.favorite_action.triggered.connect(self._toggle_favorite)
        self.addAction(self.favorite_action)
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        self.save_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self, self.search.setFocus)
        self.search_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self, self._open_command_palette)
        self.palette_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self, self._export_library_csv)
        self.export_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.workshop_shortcut = QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.tabs.setCurrentIndex(7))
        self.workshop_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.track_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self, lambda: self.tabs.setCurrentIndex(8))
        self.track_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.backup_shortcut = QShortcut(QKeySequence("Ctrl+Shift+B"), self, self._backup_current_car)
        self.backup_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.report_shortcut = QShortcut(QKeySequence("Ctrl+P"), self, lambda: self.lab_tab._export_report("txt"))
        self.report_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.reload_shortcut = QShortcut(QKeySequence("Ctrl+R"), self, self._reload_current)
        self.reload_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.diagnostic_shortcut = QShortcut(QKeySequence("Ctrl+I"), self, lambda: self.tabs.setCurrentIndex(4))
        self.diagnostic_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.upgrade_shortcut = QShortcut(QKeySequence("Ctrl+M"), self, lambda: self._go_to_tab(9))
        self.upgrade_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        for number in range(1, 10):
            tab_shortcut = QShortcut(
                QKeySequence(f"Ctrl+{number}"), self, lambda index=number - 1: self._go_to_tab(index)
            )
            tab_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.previous_car_shortcut = QShortcut(QKeySequence("Alt+Up"), self, lambda: self._step_car(-1))
        self.previous_car_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.next_car_shortcut = QShortcut(QKeySequence("Alt+Down"), self, lambda: self._step_car(1))
        self.next_car_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self, lambda: self._cycle_tab(1))
        self.next_tab_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.previous_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, lambda: self._cycle_tab(-1))
        self.previous_tab_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.guide_shortcut = QShortcut(QKeySequence("F1"), self, self._show_guide)
        self.guide_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.clear_filters_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._clear_filters)
        self.clear_filters_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.copy_name_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._copy_car_name)
        self.copy_name_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.focus_list_shortcut = QShortcut(QKeySequence("Ctrl+L"), self, self.car_list.setFocus)
        self.focus_list_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.recent_shortcut = QShortcut(QKeySequence("Ctrl+Shift+H"), self, self._show_recent_cars)
        self.recent_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.clear_recent_shortcut = QShortcut(QKeySequence("Ctrl+Shift+L"), self, self._clear_recent_cars)
        self.clear_recent_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.favorite_filter_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self, self.favorite_filter.toggle)
        self.favorite_filter_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.editable_filter_shortcut = QShortcut(QKeySequence("Ctrl+Shift+E"), self, self.editable_filter.toggle)
        self.editable_filter_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.open_folder_shortcut = QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._open_car_folder)
        self.open_folder_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.copy_path_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self, self._copy_car_path)
        self.copy_path_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.rescan_shortcut = QShortcut(QKeySequence("F5"), self, self._reload_cars)
        self.rescan_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.clear_search_shortcut = QShortcut(QKeySequence("Esc"), self.search, self.search.clear)
        self.clear_search_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.previous_favorite_shortcut = QShortcut(QKeySequence("Alt+Shift+Up"), self, lambda: self._step_favorite(-1))
        self.previous_favorite_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.next_favorite_shortcut = QShortcut(QKeySequence("Alt+Shift+Down"), self, lambda: self._step_favorite(1))
        self.next_favorite_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.random_car_shortcut = QShortcut(QKeySequence("Ctrl+Shift+N"), self, self._random_car)
        self.random_car_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.save_next_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._save_and_next)
        self.save_next_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.edge_first_shortcut = QShortcut(QKeySequence("Ctrl+Home"), self, lambda: self._go_edge_car(True))
        self.edge_first_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.edge_last_shortcut = QShortcut(QKeySequence("Ctrl+End"), self, lambda: self._go_edge_car(False))
        self.edge_last_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self, self._quit_app)
        self.quit_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.info_shortcut = QShortcut(QKeySequence("Ctrl+,"), self, self._show_info)
        self.info_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.tray_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self, self._minimize_to_tray)
        self.tray_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.ac_folder_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self, self._open_ac_folder)
        self.ac_folder_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.external_folder_shortcut = QShortcut(QKeySequence("Ctrl+Shift+G"), self, self._open_data_folder)
        self.external_folder_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.sort_shortcut = QShortcut(QKeySequence("Ctrl+Shift+K"), self, self._cycle_sort)
        self.sort_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.forget_recent_shortcut = QShortcut(QKeySequence("Ctrl+Shift+U"), self, self._forget_recent_car)
        self.forget_recent_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.last_car_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Y"), self, self._open_last_car)
        self.last_car_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.delete_favorite_shortcut = QShortcut(QKeySequence("Delete"), self.car_list, self._toggle_favorite)
        self.delete_favorite_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self._recent_menu = QMenu(self)
        self._refresh_utility_buttons()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(58)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        # La cabecera comparte marca con el icono de ventana y el splash.
        layout.addWidget(widgets.BrandMark(), 0)

        # linea grafica de identidad
        stripes = QWidget()
        stripes_layout = QVBoxLayout(stripes)
        stripes_layout.setContentsMargins(0, 0, 0, 0)
        stripes_layout.setSpacing(4)
        stripes_layout.addStretch(1)
        for width in (30, 22, 14):
            stripe = QLabel()
            stripe.setObjectName("appStripe")
            stripe.setFixedSize(width, 4)
            stripes_layout.addWidget(stripe)
        stripes_layout.addStretch(1)
        layout.addWidget(stripes, 0)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(0)
        title = QLabel(APP_NAME.upper())
        title.setObjectName("appTitle")
        subtitle = QLabel("TALLER DE COCHES · ASSETTO CORSA")
        subtitle.setObjectName("appSubtitle")
        # Puede recortarse en ventanas estrechas en vez de empujar toda la cabecera.
        subtitle.setMinimumWidth(1)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        layout.addLayout(titles, 0)

        layout.addStretch(1)

        # Buscador global: abre la paleta de comandos (páginas y acciones).
        search_button = QPushButton("⌕  Buscar herramienta…  Ctrl+K")
        search_button.setObjectName("headerSearch")
        search_button.setMinimumWidth(200)
        search_button.setToolTip("Paleta de comandos: páginas y acciones (Ctrl+K)")
        search_button.clicked.connect(lambda _checked=False: self._open_command_palette())
        layout.addWidget(search_button, 0)

        self.path_label = QLabel("")
        self.path_label.setObjectName("headerNote")
        self.path_label.setMinimumWidth(1)
        self.path_label.setMaximumWidth(250)
        layout.addWidget(self.path_label, 0)

        for text, slot, tip in (
            ("Recargar", self._reload_cars, "Vuelve a leer content/cars sin bloquear la interfaz"),
            (
                "Abrir data",
                self._open_data_folder,
                "Edita la carpeta data de un coche extraido",
            ),
            ("Ruta AC", self._choose_ac_root, "Si el juego no esta en la ruta de Steam"),
            ("Interfaz", self._theme_menu, "Tema carbón y oro; ajusta el tamaño de la interfaz"),
            ("Idioma", self._language_menu, "Español / English · la app se reinicia al cambiar"),
            ("Guía", self._show_guide, "Guía rápida, seguridad y atajos de teclado"),
            ("INFO", self._show_info, "Créditos y licencia de Quick Mechanic"),
        ):
            button = QPushButton(text)
            button.setObjectName("headerButton")
            button.setMinimumWidth(64)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            layout.addWidget(button, 0)
            if text == "Recargar":
                self.reload_button = button
            elif text == "Idioma":
                self.language_button = button
        return header

    def _build_car_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("carHeader")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 9)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.car_name = QLabel("Selecciona un coche")
        self.car_name.setObjectName("carName")
        self.car_brand = QLabel("")
        self.car_brand.setObjectName("carBrand")
        top.addWidget(self.car_name, 0)
        top.addWidget(self.car_brand, 0)
        top.addStretch(1)
        self.favorite_toggle = QPushButton("☆")
        self.favorite_toggle.setObjectName("iconButton")
        self.favorite_toggle.setToolTip("Marcar como favorito (Ctrl+D)")
        self.favorite_toggle.clicked.connect(self._toggle_favorite)
        top.addWidget(self.favorite_toggle, 0)
        layout.addLayout(top)

        self.pill_holder = QWidget()
        self.pill_slot = QHBoxLayout(self.pill_holder)
        self.pill_slot.setContentsMargins(0, 0, 0, 0)
        self.pill_slot.setSpacing(6)
        layout.addWidget(self.pill_holder, 0)
        return frame

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(48)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        self.footer_status = QLabel("")
        self.footer_status.setObjectName("footerStatus")
        layout.addWidget(self.footer_status, 1)

        self.revert_button = QPushButton("Descartar cambios")
        self.revert_button.setObjectName("danger")
        self.revert_button.setToolTip("Vuelve a leer los .ini del coche y tira los cambios en memoria (Ctrl+R)")
        self.revert_button.clicked.connect(self._reload_current)
        layout.addWidget(self.revert_button)
        self.undo_button = QPushButton("↶")
        self.undo_button.setObjectName("iconButton")
        self.undo_button.setToolTip("Deshacer ajuste (Ctrl+Z)")
        self.undo_button.clicked.connect(self._undo)
        layout.addWidget(self.undo_button)
        self.redo_button = QPushButton("↷")
        self.redo_button.setObjectName("iconButton")
        self.redo_button.setToolTip("Rehacer ajuste (Ctrl+Y)")
        self.redo_button.clicked.connect(self._redo)
        layout.addWidget(self.redo_button)
        self.preset_button = QPushButton("Perfiles")
        self.preset_button.setToolTip("Guardar, cargar o importar/exportar perfiles de setup")
        self.preset_button.clicked.connect(self._preset_menu)
        layout.addWidget(self.preset_button)
        self.swap_button = QPushButton("Swaps")
        self.swap_button.setObjectName("ghost")
        self.swap_button.setToolTip("Intercambiar componentes entre coches con validación y copia de seguridad")
        self.swap_button.clicked.connect(self._swap_menu)
        layout.addWidget(self.swap_button)

        self.save_button = QPushButton("Guardar todo")
        self.save_button.setObjectName("primary")
        self.save_button.setToolTip(
            "Escribe solo las lineas cambiadas; antes crea un ZIP de seguridad y conserva el .bak original (Ctrl+S)"
        )
        self.save_button.clicked.connect(self._save)
        layout.addWidget(self.save_button)
        return footer

    # ----------------------------------------------------------- lista de coches
    def _reload_cars(self) -> None:
        if self._load_thread is not None and self._load_thread.isRunning():
            self.footer_status.setText("Espera a que termine de preparar el coche actual…")
            return
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self.footer_status.setText("La biblioteca ya se está escaneando…")
            return
        if self._car is not None and self._car.changed and not self._confirm_discard():
            return
        self._load_car(None, None)
        self._meta_cache.clear()
        self.car_list.clear()
        self.car_list.setEnabled(False)
        self.list_status.setText("Escaneando carpetas y fichas de coches…")
        if hasattr(self, "reload_button"):
            self.reload_button.setEnabled(False)
        self.footer_status.setText("Leyendo la biblioteca en segundo plano; la interfaz sigue disponible…")
        if self._splash is not None:
            self._splash.set_status("LEYENDO COCHES Y FICHAS", 24)

        thread = QThread(self)
        worker = _LibraryScanWorker(self.ac_root)
        worker.moveToThread(thread)
        self._scan_worker = worker
        thread.started.connect(worker.run)
        worker.completed.connect(self._finish_car_scan)
        worker.failed.connect(self._fail_car_scan)
        worker.progress.connect(self._update_scan_progress)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda scan=thread: self._clear_scan_thread(scan))
        self._scan_thread = thread
        thread.start()

    def _clear_scan_thread(self, thread: QThread) -> None:
        if self._scan_thread is thread:
            self._scan_thread = None
            self._scan_worker = None
        if self._exit_requested:
            QTimer.singleShot(0, self.close)

    def _clear_load_thread(self, thread: QThread) -> None:
        if self._load_thread is thread:
            self._load_thread = None
            self._load_worker = None
        if self._exit_requested:
            QTimer.singleShot(0, self.close)

    @pyqtSlot(int, int)
    def _update_scan_progress(self, current: int, total: int) -> None:
        if total:
            self.list_status.setText(f"Leyendo fichas de coches… {current}/{total}")
            if self._splash is not None:
                progress = 25 + int(70 * current / total)
                self._splash.set_status(f"FICHAS DE COCHE · {current}/{total}", progress)

    @pyqtSlot(object, object)
    def _finish_car_scan(self, cars, metadata) -> None:
        self._cars = list(cars)
        self._meta_cache = dict(metadata)
        self._index_car_search_terms()
        self.dashboard_tab.set_library(self._cars)
        self._refresh_home()
        self.car_list.setEnabled(True)
        if hasattr(self, "reload_button"):
            self.reload_button.setEnabled(True)
        if self.ac_root is not None:
            self._set_path_text(f"Assetto Corsa: {self.ac_root}")
            try:
                settings.set_value("ac_root", str(self.ac_root))
            except OSError:
                pass
        else:
            self._set_path_text("Assetto Corsa no encontrado")
            self.path_label.setToolTip(
                "No se ha encontrado Assetto Corsa. Usa 'Ruta AC' para indicar la carpeta."
            )
        self.lab_tab.set_library(self._cars, self._meta_cache, self._favorites)
        self._refresh_home()
        self._update_nav_status(self._source)
        self._refresh_tracks()
        self._apply_filter()
        if self._source is None:
            self._select_last_car()
        self.footer_status.setText(f"Biblioteca lista · {len(self._cars)} coches revisados")
        if self._splash is not None and not self._splash_finish_pending:
            self._splash_finish_pending = True
            self._splash.set_status(f"BOX LISTO · {len(self._cars)} COCHES", 100)
            self._splash.finish(self)
        elif not self._background_start:
            self._schedule_startup_notices()
        if (
            self._show_guide_on_start
            and not self._background_start
            and self.isVisible()
            and not self._exit_requested
        ):
            QTimer.singleShot(180, self._show_guide)

    @pyqtSlot(str)
    def _fail_car_scan(self, message: str) -> None:
        self._cars = []
        self._meta_cache.clear()
        self._index_car_search_terms()
        self._refresh_tracks()
        self.car_list.setEnabled(True)
        if hasattr(self, "reload_button"):
            self.reload_button.setEnabled(True)
        self._apply_filter()
        self.footer_status.setText(f"No se pudo leer la biblioteca: {message}")
        if self._splash is not None and not self._splash_finish_pending:
            self._splash_finish_pending = True
            self._splash.set_status("BIBLIOTECA NO DISPONIBLE", 100)
            self._splash.finish(self)
        elif not self._background_start:
            self._schedule_startup_notices()

    def _complete_splash_finish(self) -> None:
        self._splash = None
        self._splash_finish_pending = False
        if not self._background_start:
            self._schedule_startup_notices()

    def _refresh_tracks(self) -> None:
        """Actualiza el catálogo local de circuitos sin alterar ningún archivo."""
        if self.ac_root is None:
            self._tracks = []
            self._track_scan_error = "No se ha encontrado la instalación de Assetto Corsa."
        else:
            try:
                self._tracks = tracks.scan_tracks(self.ac_root)
                self._track_scan_error = ""
            except tracks.TrackError as error:
                self._tracks = []
                self._track_scan_error = str(error)
        if hasattr(self, "track_tab"):
            self.track_tab.set_tracks(self._tracks, self._track_scan_error)

    def _open_track_folder(self, path: str) -> None:
        """Abre solo una carpeta que pertenezca a la biblioteca escaneada."""
        candidate = Path(path)
        for track in self._tracks:
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(track.folder.resolve(strict=True))
            except (OSError, RuntimeError, ValueError):
                continue
            if candidate.is_symlink() or not candidate.is_dir():
                break
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))
            return
        QMessageBox.warning(
            self,
            "Ruta de circuito no válida",
            "La carpeta ya no está disponible dentro de la biblioteca de Assetto Corsa.",
        )

    def _track_status(self, message: str) -> None:
        self.footer_status.setText(message)

    def _open_track_ini(self, path: str) -> None:
        """Abre en el editor del sistema solo un INI reconocido y seguro del circuito."""
        candidate = Path(path)
        for track in self._tracks:
            try:
                target = candidate.resolve(strict=True)
                if any(target == known.resolve(strict=True) for known in tracks.ini_files(track)):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))
                    return
            except (OSError, RuntimeError, ValueError):
                continue
        QMessageBox.warning(
            self,
            "Ruta de circuito no válida",
            "El INI ya no está disponible dentro de las ubicaciones reconocidas del circuito.",
        )

    def _export_library_csv(self) -> None:
        if not self._shown:
            QMessageBox.information(self, "Biblioteca vacía", "No hay coches visibles para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar biblioteca", "quick_mechanic_cars.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("Nombre", "Identificador", "Marca", "Clase", "Estado", "Editable", "Carpeta"))
                for car in self._shown:
                    meta = self._meta(car)
                    writer.writerow((
                        car.ui_name, car.name, meta.brand, meta.car_class, car.status,
                        "Sí" if car.editable else "No", str(car.folder),
                    ))
        except OSError as error:
            QMessageBox.warning(self, "No se pudo exportar la biblioteca", str(error))
            return
        self.footer_status.setText(f"Exportados {len(self._shown)} coches · {Path(path).name}")

    @staticmethod
    def _open_discord() -> None:
        QDesktopServices.openUrl(QUrl(DISCORD_URL))

    def _build_community_notification(self) -> QFrame:
        toast = QFrame()
        toast.setObjectName("communityNotification")
        toast.setFixedHeight(44)
        row = QHBoxLayout(toast)
        row.setContentsMargins(14, 4, 10, 4)
        row.setSpacing(10)
        badge = QLabel("QM  /  COMUNIDAD")
        badge.setObjectName("communityBadge")
        row.addWidget(badge)
        message = QLabel("Novedades, ayuda y soporte de Quick Mechanic")
        message.setObjectName("communityMessage")
        row.addWidget(message, 1)
        join = QPushButton("Discord ↗")
        join.setObjectName("heroButton")
        join.setToolTip("Abrir la invitación oficial de Discord en el navegador")
        join.clicked.connect(self._open_discord)
        join.clicked.connect(self._hide_discord_notification)
        row.addWidget(join)
        dismiss = QPushButton("×")
        dismiss.setObjectName("iconButton")
        dismiss.setFixedWidth(34)
        dismiss.setToolTip("Cerrar este aviso; volverá a aparecer al próximo inicio")
        dismiss.clicked.connect(self._hide_discord_notification)
        row.addWidget(dismiss)
        toast.hide()
        return toast

    def _show_discord_notification(self) -> None:
        if self._background_start or not self.isVisible():
            return
        self.community_notification.show()
        self._community_notification_timer.start(9000)

    def _hide_discord_notification(self) -> None:
        self._community_notification_timer.stop()
        self.community_notification.hide()

    # ------------------------------------------------------- idioma
    def _schedule_startup_notices(self) -> None:
        if self._background_start:
            return
        QTimer.singleShot(250, self._show_discord_notification)

    def _language_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("IDIOMA / LANGUAGE · se aplica al reiniciar").setEnabled(False)
        menu.addSeparator()
        for code in i18n.LANGUAGES:
            action = menu.addAction(i18n.language_label(code))
            action.setCheckable(True)
            action.setChecked(i18n.get_language() == code)
            action.triggered.connect(
                lambda _checked=False, language=code: self._set_language(language)
            )
        button = self.sender()
        if isinstance(button, QPushButton):
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _set_language(self, code: str) -> None:
        if code not in i18n.LANGUAGES or code == i18n.get_language():
            return
        i18n.set_language(code, persist=True)
        answer = QMessageBox.question(
            self,
            "Idioma cambiado",
            "El idioma se aplica al reiniciar Quick Mechanic para reconstruir la interfaz. "
            "¿Quieres reiniciar ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes and restart_application():
            return
        self.footer_status.setText("Idioma guardado · se aplicará al reiniciar la app")

    def _swap_menu(self) -> None:
        if self._source is None:
            QMessageBox.information(self, "Selecciona un coche", "Selecciona primero un coche para continuar.")
            return
        menu = QMenu(self)
        for title, kind in (
            ("Intercambiar motor…", "motor"),
            ("Intercambiar sonido…", "sonido"),
            ("Copiar transmisión…", "transmisión"),
            ("Copiar suspensión / fitment…", "fitment"),
        ):
            action = menu.addAction(title)
            enabled = kind == "sonido" or self._car is not None
            action.setEnabled(enabled)
            if not enabled:
                action.setToolTip("Este swap requiere una carpeta data/ extraída y editable")
            action.triggered.connect(lambda _checked=False, swap_kind=kind: self._start_swap(swap_kind))
        menu.addSeparator()
        backup_action = menu.addAction("Crear copia de seguridad ahora…")
        backup_action.triggered.connect(self._backup_current_car)
        restore_action = menu.addAction("Restaurar copia de seguridad…")
        restore_action.triggered.connect(self._restore_current_car)
        button = self.sender()
        if isinstance(button, QPushButton):
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _backup_current_car(self) -> None:
        if self._source is None:
            return
        try:
            archive = swaps.create_backup(self._source.folder)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "No se pudo crear el respaldo", str(error))
            return
        self.footer_status.setText(f"Respaldo creado · {archive.name}")
        QMessageBox.information(self, "Copia de seguridad creada", f"Se guardaron data/ y data.acd (si existía):\n{archive}")

    def _restore_current_car(self) -> None:
        if self._source is None:
            return
        if self._car is not None and self._car.changed and not self._confirm_discard():
            return
        backup_dir = self._source.folder / "quickmechanic_backups"
        latest = sorted(backup_dir.glob("data_backup_*.zip"), reverse=True) if backup_dir.is_dir() else []
        path, _ = QFileDialog.getOpenFileName(
            self, "Restaurar copia de seguridad", str(latest[0].parent if latest else backup_dir),
            "Respaldos Quick Mechanic (*.zip)",
        )
        if not path:
            return
        if QMessageBox.question(
            self, "Confirmar restauración",
            "Se restaurarán únicamente data/ y data.acd incluidos en el respaldo. "
            "No se eliminarán otros archivos; antes se creará otro respaldo de seguridad. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            safety = swaps.restore_backup(self._source.folder, path)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo restaurar el respaldo", str(error))
            return
        restored_data = car_data.CarData.from_car(self._source) if self._source.editable else None
        self._load_car(self._source, restored_data)
        self.footer_status.setText(f"Respaldo restaurado · respaldo de seguridad: {safety.name}")
        QMessageBox.information(self, "Restauración completada", f"Se creó un respaldo previo para deshacer: {safety}")

    def _start_swap(self, kind: str) -> None:
        target = self._source
        if target is None:
            return
        if self._car is not None and self._car.changed and not self._confirm_discard():
            return
        if kind != "sonido" and self._car is None:
            QMessageBox.information(self, "Destino no editable", "Restaura primero una copia con data/ extraída antes de aplicar un swap de física.")
            return
        candidates = self._extra_cars + self._cars
        if kind == "sonido":
            choices = [car for car in candidates if car.folder != target.folder and (car.folder / "sfx.ini").is_file()]
        else:
            choices = [car for car in candidates if car.editable and car.folder != target.folder]
        if not choices:
            QMessageBox.information(self, "Sin donantes compatibles", "Hace falta otro coche con carpeta data/ extraída y editable.")
            return
        labels = [f"{car.ui_name}  ·  {car.name}" for car in choices]
        label, accepted = QInputDialog.getItem(self, "Elegir coche donante", f"Donante para {target.ui_name}:", labels, 0, False)
        if not accepted:
            return
        donor = choices[labels.index(label)]
        try:
            plan = swaps.prepare_swap(kind, donor.folder, target.folder)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Intercambio no disponible", str(error))
            return
        details = "\n".join(f"• {path}" for path in plan.files)
        warnings = "\n\n".join(plan.warnings)
        answer = QMessageBox.question(
            self, f"Revisar intercambio · {plan.kind.title()}",
            f"Donante: {donor.ui_name}\nDestino: {target.ui_name}\n\nSe reemplazarán: {details}\n\n"
            f"{warnings}\n\nSe creará un ZIP de respaldo antes de aplicar. El coche donante no se modifica. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            archive = swaps.apply_swap(plan)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo aplicar el intercambio", str(error))
            return
        reloaded_data = car_data.CarData.from_car(target) if target.editable else None
        self._load_car(target, reloaded_data)
        self.footer_status.setText(f"{plan.kind.title()} aplicado · respaldo: {archive.name}")
        QMessageBox.information(
            self, "Intercambio aplicado",
            f"Se actualizó {target.ui_name}.\n\nRespaldo completo: {archive}\n"
            "Revisa el coche en Assetto Corsa antes de compartirlo.",
        )

    def _open_command_palette(self, query: str = "") -> None:
        dialog = CommandPalette(self._palette_commands(), self, query)
        if dialog.exec() and dialog.chosen is not None:
            dialog.chosen.action()

    def _palette_commands(self) -> list[Command]:
        pages = (
            (0, "Resumen", "Garaje"), (1, "Motor", "Ingeniería"), (2, "Caja de cambios", "Ingeniería"),
            (3, "Chasis", "Ingeniería"), (4, "Diagnóstico", "Diagnóstico"), (5, "Asistencias", "Ingeniería"),
            (6, "Avanzado", "Ingeniería"), (7, "Taller", "Herramientas"), (8, "Circuitos", "Herramientas"),
            (9, "Mejoras", "Herramientas"),
        )
        commands = [
            Command(title, f"Página · {group}", lambda page=index: self.tabs.setCurrentIndex(page),
                    enabled=self.tabs.isTabEnabled(index), keywords=self.tabs.tabToolTip(index))
            for index, title, group in pages
        ]
        commands += [
            Command("Buscar coche", "Garaje", self.search.setFocus, keywords="filtrar lista coleccion"),
            Command("Exportar biblioteca a CSV", "Garaje", self._export_library_csv, keywords="excel hoja"),
            Command("Alternar favorito", "Garaje", self._toggle_favorite, keywords="estrella"),
            Command("Guardar cambios", "Archivo", self._save, keywords="grabar escribir"),
            Command("Deshacer", "Edición", self._undo, keywords="atras"),
            Command("Rehacer", "Edición", self._redo, keywords="adelante"),
        ]
        return commands

    def _nav_transition(self) -> None:
        self._sync_nav_selection(self.tabs.currentIndex())

    def _sync_nav_selection(self, index: int) -> None:
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)
        titles = self.TAB_TITLES
        sections = ("GARAJE", "INGENIERÍA", "INGENIERÍA", "INGENIERÍA", "DIAGNÓSTICO", "INGENIERÍA", "INGENIERÍA", "HERRAMIENTAS", "HERRAMIENTAS", "HERRAMIENTAS")
        descriptions = (
            "Estado de la colección y cálculos derivados de los archivos locales del coche.",
            "Lee power.lut y permite editar sus puntos, corte, turbo y entrega de par.",
            "Ajusta relaciones y diferencial; las velocidades teóricas se muestran en una tabla.",
            "Suspensión, geometría, frenos, masa y presiones con análisis instantáneo.",
            "Ficha técnica, alertas de seguridad y estado de los archivos de física.",
            "Inspecciona ABS y control de tracción cuando están declarados por el coche.",
            "Editor experto limitado a parámetros numéricos presentes en los INI abiertos.",
            "Prestaciones, setups, historial, ajustes y respaldos del coche seleccionado.",
            "Busca circuitos instalados, layouts, metadatos y archivos de configuración en modo lectura.",
            "Stage tuning, RTO, ficha ui_car y copias de seguridad del coche seleccionado.",
        )
        self._record_recent_tool(index)
        if 0 <= index < len(titles) and hasattr(self, "page_title"):
            self.page_title.setText(titles[index])
            self.page_eyebrow.setText(f"{sections[index]}  ›  {titles[index].upper()}")
            self.page_description.setText(descriptions[index])
        self._animate_page()

    def _animate_page(self) -> None:
        page = self.tabs.currentWidget() if hasattr(self, "tabs") else None
        if page is None:
            return
        for old in self._animations:
            old.stop()
        self._animations.clear()
        current_effect = page.graphicsEffect()
        if isinstance(current_effect, QGraphicsOpacityEffect):
            page.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(170)
        animation.setStartValue(0.74)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda target=page: target.setGraphicsEffect(None))
        self._animations.append(animation)
        animation.start()

    def _show_guide(self) -> None:
        dialog = QuickGuideDialog(
            self,
            first_run=self._show_guide_on_start,
            show_on_start=self._show_guide_on_start,
        )
        if dialog.exec():
            self._show_guide_on_start = dialog.show_on_start
        try:
            settings.set_value("show_guide", self._show_guide_on_start)
        except OSError:
            pass

    def _build_guide_strip(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("guideStrip")
        row = QHBoxLayout(strip)
        row.setContentsMargins(12, 7, 12, 7)
        label = QLabel("COMUNIDAD  /  Novedades, ayuda y guía rápida")
        label.setObjectName("guideStripText")
        row.addWidget(label, 1)
        discord = QPushButton("Discord ↗")
        discord.setObjectName("ghost")
        discord.setToolTip("Abrir la comunidad oficial para ayuda y avisos de versiones")
        discord.clicked.connect(self._open_discord)
        row.addWidget(discord)
        button = QPushButton("Abrir guía")
        button.setObjectName("ghost")
        button.clicked.connect(self._show_guide)
        row.addWidget(button)
        return strip

    def _set_content_manager_path(self, path: str) -> None:
        candidate = content_manager.find_executable(path)
        self.content_manager_path = candidate
        try:
            settings.set_value("content_manager_path", str(candidate or path))
        except OSError:
            pass
        self.cm_panel.set_executable(candidate)

    def _sync_library(self) -> None:
        """Reindexa coches y circuitos tras operar en Content Manager."""
        if self.ac_root is None:
            self._choose_ac_root()
            return
        self._refresh_tracks()
        self._reload_cars()
        self.footer_status.setText(f"Biblioteca sincronizada · {len(self._cars)} coches y {len(self._tracks)} circuitos")

    def _set_path_text(self, text: str) -> None:
        self.path_label.setToolTip(text)
        self.path_label.setText(
            self.path_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, 320)
        )

    def _index_car_search_terms(self) -> None:
        self._search_terms = {}
        for car in self._extra_cars + self._cars:
            meta = self._meta(car)
            self._search_terms[car.folder] = " ".join(
                (car.ui_name, car.name, meta.brand, meta.car_class, meta.country)
            ).casefold()

    def _apply_filter(self) -> None:
        self._save_filters()
        needle = self.search.text().strip().casefold()
        candidates = self._extra_cars + self._cars
        if needle:
            self._shown = [
                car
                for car in candidates
                if needle in car.ui_name.casefold()
                or needle in car.name.casefold()
                or needle in self._search_terms.get(car.folder, "")
            ]
        else:
            self._shown = list(candidates)

        favorites_only = self.favorite_filter.isChecked()
        if favorites_only:
            self._shown = [car for car in self._shown if car.name in self._favorites]
        if self.editable_filter.isChecked():
            self._shown = [car for car in self._shown if car.editable]

        self._shown.sort(key=self._sort_key)
        selected_key = (
            (self._source.name, self._source.folder) if self._source is not None else None
        )
        self.car_list.blockSignals(True)
        self.car_list.clear()
        for car in self._shown:
            item = QListWidgetItem(self._car_item_text(car, dirty=self._is_dirty(car)))
            item.setToolTip(f"{car.folder}\nEstado: {car.status}")
            item.setSizeHint(QSize(0, 26))
            self.car_list.addItem(item)
        self._visible_car_keys = [(car.name, car.folder) for car in self._shown]
        if selected_key is not None:
            for row, car in enumerate(self._shown):
                if (car.name, car.folder) == selected_key:
                    self.car_list.setCurrentRow(row)
                    break
        self.car_list.blockSignals(False)

        editable = sum(1 for car in candidates if car.editable)
        filters = []
        if favorites_only:
            filters.append("favoritos")
        if self.editable_filter.isChecked():
            filters.append("editables")
        suffix = f" · filtro: {', '.join(filters)}" if filters else ""
        self.list_status.setText(
            f"{len(self._shown)} de {len(candidates)} coches · {editable} editables · "
            f"{len(self._favorites)} favoritos{suffix}"
        )

    def _go_to_tab(self, index: int) -> None:
        """Ctrl+1..9: cambia a la pestaña si existe y está disponible."""
        if 0 <= index < self.tabs.count() and self.tabs.isTabEnabled(index):
            self.tabs.setCurrentIndex(index)

    def _step_car(self, delta: int) -> None:
        """Alt+Arriba/Abajo: pasa al coche anterior o siguiente de la lista visible."""
        count = self.car_list.count()
        if count == 0:
            return
        row = self.car_list.currentRow()
        if row < 0:
            target = 0 if delta > 0 else count - 1
        else:
            target = (row + delta) % count
        self.car_list.setCurrentRow(target)

    def _cycle_tab(self, step: int) -> None:
        """Ctrl+Tab / Ctrl+Shift+Tab: pasa a la pestaña siguiente o anterior disponible."""
        count = self.tabs.count()
        index = self.tabs.currentIndex()
        for _ in range(count):
            index = (index + step) % count
            if self.tabs.isTabEnabled(index):
                self.tabs.setCurrentIndex(index)
                return

    def _clear_filters(self) -> None:
        """Ctrl+Shift+F: borra la búsqueda y los filtros de la lista de coches."""
        self.search.clear()
        self.favorite_filter.setChecked(False)
        self.editable_filter.setChecked(False)
        self._apply_filter()
        self.footer_status.setText("Filtros borrados")

    def _open_car_folder(self) -> None:
        """Ctrl+Shift+O: abre la carpeta del coche actual en el Explorador."""
        if self._source is None:
            self.footer_status.setText("No hay ningún coche seleccionado")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._source.folder)))

    def _copy_car_path(self) -> None:
        """Ctrl+Shift+P: copia la ruta de la carpeta del coche actual."""
        if self._source is None:
            self.footer_status.setText("No hay ningún coche seleccionado")
            return
        QApplication.clipboard().setText(str(self._source.folder))
        self.footer_status.setText("Ruta copiada al portapapeles")

    def _step_favorite(self, delta: int) -> None:
        """Alt+Shift+Arriba/Abajo: pasa al favorito anterior o siguiente de la lista visible."""
        count = len(self._visible_car_keys)
        if count == 0:
            return
        start = self.car_list.currentRow()
        if start < 0:
            start = 0 if delta > 0 else count
        for step in range(1, count + 1):
            row = (start + delta * step) % count
            if self._visible_car_keys[row][0] in self._favorites:
                self.car_list.setCurrentRow(row)
                return
        self.footer_status.setText("No hay favoritos en la lista visible")

    def _random_car(self) -> None:
        """Ctrl+Shift+N: elige al azar un coche de la lista visible, distinto del actual."""
        count = len(self._visible_car_keys)
        if count == 0:
            return
        current = self.car_list.currentRow()
        choices = [row for row in range(count) if row != current] or [0]
        self.car_list.setCurrentRow(random.choice(choices))

    def _save_and_next(self) -> None:
        """Ctrl+Shift+S: guarda los cambios del coche actual y pasa al siguiente."""
        if self._car is not None and self._car.changed:
            self._save()
        self._step_car(1)

    def _restore_filters(self) -> None:
        """Recupera la búsqueda y los filtros de la sesión anterior."""
        text = settings.get("search_text", "")
        if isinstance(text, str):
            self.search.setText(text)
        self.favorite_filter.setChecked(bool(settings.get("filter_favorites", False)))
        self.editable_filter.setChecked(bool(settings.get("filter_editable", False)))

    def _save_filters(self) -> None:
        try:
            settings.set_value("search_text", self.search.text())
            settings.set_value("filter_favorites", self.favorite_filter.isChecked())
            settings.set_value("filter_editable", self.editable_filter.isChecked())
        except OSError:
            pass

    def _select_last_car(self) -> None:
        """Selecciona el último coche abierto si sigue en la lista visible."""
        folder = settings.get("last_car", "")
        for row, (_name, car_folder) in enumerate(self._visible_car_keys):
            if str(car_folder) == folder:
                self.car_list.setCurrentRow(row)
                return

    def _copy_car_name(self) -> None:
        """Ctrl+Shift+C: copia el nombre visible del coche actual al portapapeles."""
        if self._source is None:
            self.footer_status.setText("No hay ningún coche seleccionado")
            return
        QApplication.clipboard().setText(self._source.ui_name)
        self.footer_status.setText("Nombre copiado al portapapeles")

    def _remember_recent(self, source: ac_scanner.Car) -> None:
        key = str(source.folder)
        self._recent_cars = [folder for folder in self._recent_cars if folder != key]
        self._recent_cars.insert(0, key)
        del self._recent_cars[self.RECENT_LIMIT:]
        try:
            settings.set_value("recent_cars", list(self._recent_cars))
        except OSError:
            pass

    def _show_recent_cars(self) -> None:
        """Ctrl+Shift+H: menú con los últimos coches abiertos."""
        cars = {str(car.folder): car for car in self._extra_cars + self._cars}
        recent = [cars[folder] for folder in self._recent_cars if folder in cars]
        if not recent:
            self.footer_status.setText("Todavía no has abierto ningún coche")
            return
        if self._recent_menu is None:
            self._recent_menu = QMenu(self)
        menu = self._recent_menu
        menu.clear()
        for car in recent:
            action = menu.addAction(car.ui_name)
            action.triggered.connect(lambda _checked=False, folder=str(car.folder): self._open_car_by_folder(folder))
        menu.popup(self.mapToGlobal(self.rect().center()))

    def _update_nav_status(self, source: ac_scanner.Car | None) -> None:
        """Bloque de estado del coche activo en la barra lateral."""
        if not hasattr(self, "nav_car_status"):
            return
        if source is None:
            self.nav_car_status.setText("Ningún coche seleccionado\nElige uno en la colección")
            return
        if source.editable:
            state = "Editable · data/ extraída"
        elif source.has_acd:
            state = "Bloqueado · data.acd"
        else:
            state = "Sin carpeta data/"
        star = "★ " if source.name in self._favorites else ""
        self.nav_car_status.setText(f"{star}{source.ui_name}\n{state}")

    def _refresh_home(self) -> None:
        """Actualiza las tarjetas de la pantalla de inicio: recientes, favoritos y herramientas."""
        if not hasattr(self, "dashboard_tab"):
            return
        cars = {str(car.folder): car for car in self._extra_cars + self._cars}
        recent = [(folder, cars[folder].ui_name) for folder in self._recent_cars if folder in cars]
        favorites = sorted(
            ((str(car.folder), car.ui_name) for car in self._cars if car.name in self._favorites),
            key=lambda item: item[1].casefold(),
        )
        tools = [(index, self.TAB_TITLES[index]) for index in self._recent_tools]
        self.dashboard_tab.set_home(recent, favorites, tools)

    def _record_recent_tool(self, index: int) -> None:
        """Recuerda la última herramienta abierta (la pantalla de inicio no cuenta)."""
        if index <= 0 or index >= len(self.TAB_TITLES):
            return
        self._recent_tools = [item for item in self._recent_tools if item != index]
        self._recent_tools.insert(0, index)
        del self._recent_tools[self.RECENT_TOOL_LIMIT:]
        try:
            settings.set_value("recent_tools", list(self._recent_tools))
        except OSError:
            pass

    def _home_action(self, action: str) -> None:
        """Acciones rápidas de la pantalla de inicio; reutilizan los mismos atajos del menú."""
        if action == "palette":
            self._open_command_palette()
        elif action == "random":
            self._random_car()
        elif action == "export":
            self._export_library_csv()
        elif action == "sync":
            self._sync_library()

    def _sort_key(self, car: ac_scanner.Car) -> tuple:
        """Orden de la lista según el modo elegido con Ctrl+Shift+K."""
        name = car.ui_name.casefold()
        if self._sort_mode == "favorites":
            return (car.name not in self._favorites, name)
        if self._sort_mode == "editable":
            return (not car.editable, name)
        if self._sort_mode == "recent":
            key = str(car.folder)
            position = self._recent_cars.index(key) if key in self._recent_cars else len(self._recent_cars)
            return (position, name)
        return (name,)

    def _cycle_sort(self) -> None:
        """Ctrl+Shift+K: pasa al siguiente orden de la lista."""
        index = self.SORT_MODES.index(self._sort_mode)
        self._sort_mode = self.SORT_MODES[(index + 1) % len(self.SORT_MODES)]
        try:
            settings.set_value("sort_mode", self._sort_mode)
        except OSError:
            pass
        self._apply_filter()
        self.footer_status.setText(f"Orden: {self.SORT_LABELS[self._sort_mode]}")

    def _go_edge_car(self, first: bool) -> None:
        """Ctrl+Home / Ctrl+End: primer o último coche de la lista visible."""
        count = self.car_list.count()
        if count:
            self.car_list.setCurrentRow(0 if first else count - 1)

    def _open_last_car(self) -> None:
        """Ctrl+Shift+Y: vuelve al último coche abierto, quitando filtros si hace falta."""
        folder = settings.get("last_car", "")
        if not isinstance(folder, str) or not folder:
            self.footer_status.setText("Todavía no hay ningún coche abierto en una sesión anterior")
            return
        self._open_car_by_folder(folder)

    def _quit_app(self) -> None:
        """Ctrl+Q: cierra Quick Mechanic; closeEvent pide confirmación si hay cambios."""
        self._exit_from_tray()

    def _minimize_to_tray(self) -> None:
        """Ctrl+Shift+M: oculta la ventana a la bandeja, o la minimiza si no hay bandeja."""
        if self._tray is not None:
            self.hide()
        else:
            self.showMinimized()

    def _open_ac_folder(self) -> None:
        """Ctrl+Shift+A: abre la carpeta raíz de Assetto Corsa."""
        if self.ac_root is None:
            self.footer_status.setText("Assetto Corsa no está configurado")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ac_root)))

    def _forget_recent_car(self) -> None:
        """Ctrl+Shift+U: quita el coche actual del historial de recientes."""
        if self._source is None:
            self.footer_status.setText("No hay ningún coche seleccionado")
            return
        key = str(self._source.folder)
        if key not in self._recent_cars:
            self.footer_status.setText("Este coche no está en recientes")
            return
        self._recent_cars = [folder for folder in self._recent_cars if folder != key]
        try:
            settings.set_value("recent_cars", list(self._recent_cars))
        except OSError:
            pass
        if self._sort_mode == "recent":
            self._apply_filter()
        self.footer_status.setText("Coche quitado de recientes")

    def _is_dirty(self, car: ac_scanner.Car) -> bool:
        return car is self._source and self._car is not None and self._car.changed

    def _car_item_text(self, car: ac_scanner.Car, dirty: bool = False) -> str:
        favorite = "★  " if car.name in self._favorites else ""
        text = favorite + (car.ui_name if car.editable else f"{car.ui_name}   ·   data.acd")
        return f"● {text}" if dirty else text

    def _update_dirty_marker(self) -> None:
        """Marca con ● en la lista los coches con cambios sin guardar."""
        for row, car in enumerate(self._shown):
            item = self.car_list.item(row)
            if item is None:
                continue
            text = self._car_item_text(car, dirty=self._is_dirty(car))
            if item.text() != text:
                item.setText(text)

    def _refresh_window_title(self) -> None:
        base = f"{APP_NAME}  ·  VEHICLE ENGINEERING"
        if self._source is not None and self._car is not None and self._car.changed:
            self.setWindowTitle(f"● {self._source.ui_name} · {base}")
        else:
            self.setWindowTitle(base)

    def _car_list_menu(self, pos: QPoint) -> None:
        """Menú contextual del coche bajo el cursor en la lista."""
        item = self.car_list.itemAt(pos)
        if item is None:
            return
        self.car_list.setCurrentRow(self.car_list.row(item))
        if self._source is None:
            return
        menu = QMenu(self)
        for label, slot in (
            ("Alternar favorito", self._toggle_favorite),
            ("Copiar nombre", self._copy_car_name),
            ("Copiar ruta", self._copy_car_path),
            ("Abrir carpeta", self._open_car_folder),
            ("Quitar de recientes", self._forget_recent_car),
        ):
            action = menu.addAction(label)
            action.triggered.connect(slot)
        menu.exec(self.car_list.mapToGlobal(pos))

    def _clear_recent_cars(self) -> None:
        """Ctrl+Shift+L: borra el historial de coches recientes."""
        self._recent_cars = []
        try:
            settings.set_value("recent_cars", [])
        except OSError:
            pass
        self.footer_status.setText("Historial de coches recientes borrado")

    def _open_car_by_folder(self, folder: str) -> None:
        car = next((item for item in self._extra_cars + self._cars if str(item.folder) == folder), None)
        if car is None:
            return
        key = (car.name, car.folder)
        if key not in self._visible_car_keys:
            self.search.clear()
            self.favorite_filter.setChecked(False)
            self.editable_filter.setChecked(False)
            self._apply_filter()
        if key in self._visible_car_keys:
            self.car_list.setCurrentRow(self._visible_car_keys.index(key))

    def _restore_last_tab(self) -> None:
        index = settings.get("last_tab")
        if isinstance(index, int) and not isinstance(index, bool) and self.tabs.isTabEnabled(index):
            self.tabs.setCurrentIndex(index)

    def _on_car_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_car_keys):
            return
        if self._load_thread is not None and self._load_thread.isRunning():
            # Mientras se prepara un coche no se cambia de coche: la lista conserva el foco
            # y vuelve a mostrar el coche que ya esta cargado.
            self.footer_status.setText("Espera: ya se está preparando otro coche…")
            self._reselect(self._source)
            return
        name, folder = self._visible_car_keys[row]
        source = next((car for car in self._extra_cars + self._cars if car.name == name and car.folder == folder), None)
        if source is None:
            return
        if self._car is not None and self._car.changed and not self._confirm_discard():
            self._reselect(self._source)
            return
        try:
            settings.set_value("last_car", str(source.folder))
        except OSError:
            pass
        self._car_request += 1
        if acd.needs_unpack(Path(source.folder)):
            # QuickBMS puede tardar minutos: se ejecuta fuera del hilo de la interfaz
            self._start_car_unpack(self._car_request, source)
            return
        try:
            data = car_data.CarData.from_car(source) if source.editable else None
            self._load_car(source, data)
        except Exception as error:  # un coche con datos malformados no debe cerrar la aplicacion
            self._show_car_load_error(source, error)
            return
        self._finish_car_selection(source)

    def _finish_car_selection(self, source: ac_scanner.Car) -> None:
        self._remember_recent(source)
        self._refresh_home()
        if self._sort_mode == "recent":
            self._apply_filter()
        self._update_dirty_marker()

    def _set_car_busy(self, busy: bool) -> None:
        """Bloquea lista, pestañas y recarga mientras un coche se desempaqueta."""
        self.tabs.setEnabled(not busy)
        if hasattr(self, "reload_button"):
            self.reload_button.setEnabled(not busy)

    def _start_car_unpack(self, token: int, source: ac_scanner.Car) -> None:
        if self._load_thread is not None and self._load_thread.isRunning():
            self.footer_status.setText("Espera: ya se está preparando otro coche…")
            return
        self.footer_status.setText(f"Desempaquetando data.acd de {source.ui_name}… (puede tardar unos minutos)")
        self._set_car_busy(True)
        thread = QThread(self)
        worker = _CarLoadWorker(token, source)
        worker.moveToThread(thread)
        self._load_worker = worker
        thread.started.connect(worker.run)
        worker.completed.connect(self._finish_car_unpack)
        worker.failed.connect(self._fail_car_unpack)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda loading=thread: self._clear_load_thread(loading))
        self._load_thread = thread
        thread.start()

    @pyqtSlot(int, object, object, object, str)
    def _finish_car_unpack(self, token: int, source: ac_scanner.Car, fresh: ac_scanner.Car,
                           data, message: str) -> None:
        self._set_car_busy(False)
        self._replace_cached_car(source, fresh)
        if message:
            self.footer_status.setText(message)
        if token != self._car_request:
            return  # el usuario ya eligió otro coche: solo se actualiza la caché
        self._apply_filter()
        self._reselect(fresh)
        try:
            self._load_car(fresh, data)
        except Exception as error:  # noqa: BLE001 - un coche malformado no cierra la aplicacion
            self._show_car_load_error(fresh, error)
            return
        self._finish_car_selection(fresh)

    @pyqtSlot(int, object, str)
    def _fail_car_unpack(self, token: int, source: ac_scanner.Car, message: str) -> None:
        self._set_car_busy(False)
        if token != self._car_request:
            return
        self._show_car_load_error(source, RuntimeError(message))

    def _replace_cached_car(self, source: ac_scanner.Car, fresh: ac_scanner.Car) -> None:
        if fresh is source:
            return
        for cars in (self._cars, self._extra_cars):
            for index, car in enumerate(cars):
                if car.folder == source.folder and car.name == source.name:
                    cars[index] = fresh

    def _show_car_load_error(self, source: ac_scanner.Car, error: Exception) -> None:
        """Deja la aplicacion usable tras un fallo al cargar un coche."""
        try:
            # Restablece las pestañas a estado vacio: no pueden quedar datos a medio cargar.
            self._load_car(None, None)
        except Exception:  # noqa: BLE001 - recuperacion; el aviso de abajo informa al usuario
            pass
        self._source = None
        self._car = None
        self._update_car_header()
        self._refresh_footer()
        self.banner.setText(
            f"No se pudo cargar '{source.ui_name}': {error}. Revisa los archivos del coche "
            "o restaura data.acd.bak si lo has modificado."
        )
        self.banner.show()
        self.footer_status.setText(f"Error al cargar {source.ui_name}")

    def _reselect(self, source: ac_scanner.Car | None) -> None:
        if source is None:
            return
        key = (source.name, source.folder)
        try:
            row = self._visible_car_keys.index(key)
        except ValueError:
            return
        self.car_list.blockSignals(True)
        self.car_list.setCurrentRow(row)
        self.car_list.blockSignals(False)

    def _load_car(self, source: ac_scanner.Car | None, data: car_data.CarData | None) -> None:
        self._source = source
        self._car = data
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab):
            tab.load(data)
        self.lab_tab.load(data)
        self.upgrade_tab.load(source)
        self.info_tab.load(data, source.status if source else "", self._meta(source))

        self.tabs.setTabEnabled(0, True)
        for index in (1, 2, 3, 5, 6, 7, 9):
            self.tabs.setTabEnabled(index, data is not None)
            button = self.nav_group.button(index)
            if button is not None:
                button.setEnabled(data is not None)
        self.tabs.setTabEnabled(4, True)
        diagnostic_button = self.nav_group.button(4)
        if diagnostic_button is not None:
            diagnostic_button.setEnabled(True)
        summary_button = self.nav_group.button(0)
        if summary_button is not None:
            summary_button.setEnabled(True)
        self.dashboard_tab.load(data)
        self._reset_history()
        self._refresh_utility_buttons()

        self._update_car_header()

        if source is not None and data is None:
            self.tabs.setCurrentWidget(self.info_tab)
            self.banner.setText(
                f"'{source.ui_name}' guarda su fisica dentro de data.acd. Extraela con Content "
                "Manager (boton derecho en el coche → Data → Unpack) y pulsa 'Recargar lista', "
                "o usa 'Abrir carpeta data...' si ya la tienes extraida."
            )
            self.banner.show()
        else:
            self.banner.hide()
            if data is not None:
                self.tabs.setCurrentIndex(0)
        self._refresh_footer()

    # ------------------------------------------------------- cabecera del coche
    def _meta(self, source: ac_scanner.Car | None) -> skins.CarMeta | None:
        if source is None:
            return None
        if source.folder not in self._meta_cache:
            self._meta_cache[source.folder] = skins.read_car_meta(source.folder)
        return self._meta_cache[source.folder]

    def _update_car_header(self) -> None:
        self._update_nav_status(self._source)
        widgets.clear_layout(self.pill_slot)
        source = self._source
        if source is None:
            self.car_name.setText("Selecciona un coche")
            self.car_brand.setText("")
            self.favorite_toggle.setText("☆")
            self.favorite_toggle.setEnabled(False)
            self.preview.clear()
            return
        self.favorite_toggle.setEnabled(True)

        meta = self._meta(source)
        data = self._car
        parts = [part for part in (meta.brand, meta.car_class.upper(), source.name) if part]
        self.car_brand.setText("  ·  ".join(parts))

        pills: list[tuple[str, str]] = []
        if data is not None:
            pills.append((data.drive_type, "accent"))
            pills.append((f"{data.gear_count} marchas", "info"))
            power = data.peak_power()[1]
            if power:
                pills.append((f"{power:.0f} CV", "ok"))
            torque = data.peak_torque()[1]
            if torque:
                pills.append((f"{torque:.0f} Nm", "dato"))
            if data.mass:
                pills.append((f"{data.mass:.0f} kg", "muted"))
            if data.has_turbo:
                pills.append(("Turbo", "aviso"))
        else:
            pills.append(("solo data.acd", "peligro"))
            pills.append(("no editable", "muted"))
        for text, tone in pills:
            self.pill_slot.addWidget(widgets.Pill(text, tone), 0)
        self.pill_slot.addStretch(1)

        favorite = source.name in self._favorites
        self.car_name.setText(source.ui_name)
        self.favorite_toggle.setText("★" if favorite else "☆")
        self.favorite_toggle.setToolTip(
            "Quitar de favoritos (Ctrl+D)" if favorite else "Marcar como favorito (Ctrl+D)"
        )
        self.preview.load(
            source.folder,
            title=source.ui_name,
            subtitle=meta.subtitle or source.name,
            badge=meta.badge,
            preferred_skin=self._skin_choices.get(source.name, ""),
        )

    def _remember_skin(self, skin_name: str) -> None:
        """Guarda la skin elegida para volver a ella al reabrir el coche."""
        if self._source is None or not skin_name:
            return
        if self._skin_choices.get(self._source.name) == skin_name:
            return
        self._skin_choices[self._source.name] = skin_name
        try:
            settings.set_value("skin_choices", self._skin_choices)
        except OSError:
            pass

    # ------------------------------------------------------------------ acciones
    def _restore_window_state(self) -> None:
        app = QApplication.instance()
        factor = settings.get("ui_scale", 1.0)
        if factor in (0.9, 1.0, 1.1, 1.2):
            font = QFont(theme.preferred_font_family())
            font.setPointSizeF(9.0 * float(factor))
            app.setFont(font)
        geometry = settings.get("window_geometry")
        state = settings.get("window_state")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(str(geometry).encode("ascii")))
        if state:
            self.restoreState(QByteArray.fromBase64(str(state).encode("ascii")))

    def _on_editor_changed(self) -> None:
        self._refresh_footer()
        if self._history_applying or self._car is None:
            return
        current = self._car.setup_snapshot()
        if self._history and current == self._history[self._history_index]:
            return
        self._history = self._history[: self._history_index + 1]
        self._history.append(current)
        if len(self._history) > 60:
            self._history.pop(0)
        self._history_index = len(self._history) - 1
        self._refresh_utility_buttons()
        self.dashboard_tab.load(self._car)

    def _reset_history(self) -> None:
        self._history_applying = True
        self._history = [self._car.setup_snapshot()] if self._car is not None else []
        self._history_index = 0 if self._history else -1
        self._history_applying = False

    def _refresh_utility_buttons(self) -> None:
        can_undo = self._history_index > 0
        can_redo = 0 <= self._history_index < len(self._history) - 1
        if hasattr(self, "undo_button"):
            self.undo_button.setEnabled(can_undo)
            self.redo_button.setEnabled(can_redo)
            self.preset_button.setEnabled(self._car is not None)
            self.undo_action.setEnabled(can_undo)
            self.redo_action.setEnabled(can_redo)
            self.favorite_action.setEnabled(self._source is not None)

    def _apply_history(self, index: int) -> None:
        if self._car is None or not 0 <= index < len(self._history):
            return
        self._history_applying = True
        try:
            self._car.restore_setup(self._history[index])
            for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab):
                tab.load(self._car)
            self.lab_tab.load(self._car)
            self.dashboard_tab.load(self._car)
            self.info_tab.load(self._car, self._source.status if self._source else "", self._meta(self._source))
            self._update_car_header()
            self._history_index = index
        finally:
            self._history_applying = False
        self._refresh_footer()
        self._refresh_utility_buttons()

    def _undo(self) -> None:
        if self._history_index > 0:
            self._apply_history(self._history_index - 1)

    def _redo(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._apply_history(self._history_index + 1)

    def _toggle_favorite(self) -> None:
        if self._source is None:
            return
        name = self._source.name
        if name in self._favorites:
            self._favorites.remove(name)
        else:
            self._favorites.add(name)
        try:
            settings.set_value("favorites", sorted(self._favorites))
        except OSError:
            pass
        self._update_car_header()
        self._apply_filter()
        self.lab_tab.set_library(self._cars, self._meta_cache, self._favorites)
        self._refresh_home()
        self._update_nav_status(self._source)

    def _preset_menu(self) -> None:
        if self._car is None:
            return
        menu = QMenu(self)
        save_action = menu.addAction("Guardar perfil actual…")
        drift_action = menu.addAction("Aplicar preset Drift adaptable…")
        drift_action.triggered.connect(self._apply_drift_preset)
        load_menu = menu.addMenu("Cargar perfil")
        available = presets.list_presets(self._car.name)
        if available:
            for name in available:
                action = load_menu.addAction(name)
                action.triggered.connect(lambda _checked=False, preset_name=name: self._load_preset(preset_name))
        else:
            empty = load_menu.addAction("Sin perfiles guardados")
            empty.setEnabled(False)
        menu.addSeparator()
        import_action = menu.addAction("Importar perfil JSON…")
        export_action = menu.addAction("Exportar perfil actual…")
        delete_action = menu.addAction("Eliminar perfil guardado…")
        save_action.triggered.connect(self._save_preset)
        import_action.triggered.connect(self._import_preset)
        export_action.triggered.connect(self._export_preset)
        delete_action.triggered.connect(self._delete_preset)
        menu.exec(self.preset_button.mapToGlobal(self.preset_button.rect().bottomLeft()))

    def _apply_drift_preset(self) -> None:
        if self._car is None:
            return
        answer = QMessageBox.question(
            self, "Preset Drift adaptable",
            "Se ajustarán solo parámetros compatibles ya presentes en este coche; "
            "los cambios quedarán en memoria, sin guardar en disco. Es una base orientativa, "
            "no una puesta a punto universal. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = drift.apply(self._car)
        if not result.changed_count:
            QMessageBox.information(self, "Preset Drift", result.reason)
            return
        self._load_current_views()
        self._record_external_edit()
        skipped = f"\n\nNo aplicados: {', '.join(result.skipped)}" if result.skipped else ""
        QMessageBox.information(
            self, "Preset Drift aplicado",
            f"Cambios preparados ({result.changed_count}): {', '.join(result.applied)}.\n\n"
            f"{result.reason}{skipped}\n\nRevisa en pista y pulsa Guardar todo para escribirlos.",
        )

    def _save_preset(self) -> None:
        if self._car is None:
            return
        name, accepted = QInputDialog.getText(self, "Guardar perfil", "Nombre del perfil:")
        if not accepted or not name.strip():
            return
        try:
            path = presets.save_preset(self._car.name, name, self._car.setup_snapshot())
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "No se pudo guardar el perfil", str(error))
            return
        self.footer_status.setText(f"Perfil guardado: {path.name}")

    def _load_preset(self, name: str) -> None:
        if self._car is None:
            return
        if self._car.changed and not self._confirm_discard():
            return
        try:
            snapshot = presets.load_preset(self._car.name, name)
            self._car.restore_setup(snapshot)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, "Perfil no válido", str(error))
            return
        self._load_current_views()
        self._record_external_edit()

    def _import_preset(self) -> None:
        if self._car is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Importar perfil", "", "Perfil Quick Mechanic (*.json)")
        if not path:
            return
        if self._car.changed and not self._confirm_discard():
            return
        try:
            snapshot = presets.import_preset(path)
            self._car.restore_setup(snapshot)
        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.warning(self, "Perfil no válido", str(error))
            return
        self._load_current_views()
        self._record_external_edit()

    def _load_current_views(self) -> None:
        if self._car is None:
            return
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab):
            tab.load(self._car)
        self.dashboard_tab.load(self._car)
        self.info_tab.load(self._car, self._source.status if self._source else "", self._meta(self._source))
        self._update_car_header()
        self._refresh_footer()

    def _record_external_edit(self) -> None:
        if self._car is None:
            return
        current = self._car.setup_snapshot()
        self._history = self._history[: self._history_index + 1]
        if not self._history or current != self._history[self._history_index]:
            self._history.append(current)
            if len(self._history) > 60:
                self._history.pop(0)
            self._history_index = len(self._history) - 1
        self._refresh_utility_buttons()

    def _export_preset(self) -> None:
        if self._car is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar perfil", f"{self._car.name}.json", "JSON (*.json)")
        if not path:
            return
        try:
            presets.export_preset(path, self._car.setup_snapshot())
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "No se pudo exportar", str(error))

    def _delete_preset(self) -> None:
        if self._car is None:
            return
        names = presets.list_presets(self._car.name)
        if not names:
            return
        name, accepted = QInputDialog.getItem(self, "Eliminar perfil", "Perfil:", names, 0, False)
        if accepted and presets.delete_preset(self._car.name, name):
            self.footer_status.setText(f"Perfil eliminado: {name}")

    def _theme_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("TEMA FIJO · CARBÓN / GRAFITO / ORO").setEnabled(False)
        menu.addSeparator()
        scale_menu = menu.addMenu("Tamaño de la interfaz")
        current = settings.get("ui_scale", 1.0)
        for label, factor in (("Compacta · 90%", 0.9), ("Estándar · 100%", 1.0), ("Cómoda · 110%", 1.1), ("Grande · 120%", 1.2)):
            action = scale_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current == factor)
            action.triggered.connect(lambda _checked=False, value=factor: self._set_ui_scale(value))
        menu.addSeparator()
        startup = menu.addAction("Iniciar con Windows y abrir en segundo plano")
        startup.setCheckable(True)
        startup.setEnabled(sys.platform == "win32")
        startup.blockSignals(True)
        startup.setChecked(bool(settings.get("start_with_windows", False)))
        startup.blockSignals(False)
        startup.toggled.connect(self._set_windows_startup)
        tray_option = menu.addAction("Al cerrar, dejar Quick Mechanic en la bandeja")
        tray_option.setCheckable(True)
        tray_option.setEnabled(self._tray is not None)
        tray_option.setChecked(self._close_to_tray)
        tray_option.toggled.connect(self._set_close_to_tray)
        splash = menu.addAction("Mostrar animación de carga al iniciar")
        splash.setCheckable(True)
        splash.setChecked(self._show_splash_on_start)
        splash.toggled.connect(lambda enabled: self._set_startup_option("show_loading_splash", enabled))
        guide = menu.addAction("Mostrar guía al iniciar")
        guide.setCheckable(True)
        guide.setChecked(self._show_guide_on_start)
        guide.toggled.connect(lambda enabled: self._set_startup_option("show_guide", enabled))
        button = self.sender()
        if isinstance(button, QPushButton):
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._close_to_tray = False
            return
        tray = QSystemTrayIcon(app_icon(), self)
        tray.setToolTip("Quick Mechanic · Assetto Corsa")
        menu = QMenu(self)
        open_action = menu.addAction("Abrir Quick Mechanic")
        open_action.triggered.connect(self._show_from_tray)
        menu.addSeparator()
        exit_action = menu.addAction("Salir completamente")
        exit_action.triggered.connect(self._exit_from_tray)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self._tray = tray
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(not self._close_to_tray)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self._show_guide_on_start and self._source is None and not self._background_start:
            QTimer.singleShot(180, self._show_guide)

    def _exit_from_tray(self) -> None:
        self._exit_requested = True
        self.close()

    def _set_close_to_tray(self, enabled: bool) -> None:
        self._close_to_tray = bool(enabled) and self._tray is not None
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(not self._close_to_tray)
        try:
            settings.set_value("close_to_tray", self._close_to_tray)
        except OSError:
            pass
        self.footer_status.setText(
            "Al cerrar, Quick Mechanic quedará en la bandeja" if self._close_to_tray
            else "Al cerrar, Quick Mechanic saldrá completamente"
        )

    def _set_windows_startup(self, enabled: bool) -> None:
        from .startup import set_windows_startup

        ok, message = set_windows_startup(enabled)
        if not ok:
            QMessageBox.warning(self, "Inicio con Windows", message)
            action = self.sender()
            if isinstance(action, QAction):
                action.blockSignals(True)
                action.setChecked(not enabled)
                action.blockSignals(False)
            return
        try:
            settings.set_value("start_with_windows", bool(enabled))
        except OSError as error:
            QMessageBox.warning(self, "No se pudo guardar la preferencia", str(error))
            set_windows_startup(not enabled)
            action = self.sender()
            if isinstance(action, QAction):
                action.blockSignals(True)
                action.setChecked(not enabled)
                action.blockSignals(False)
            return
        self.footer_status.setText(message)

    def _show_info(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Información · Quick Mechanic")
        dialog.setMinimumSize(600, 500)
        layout = QVBoxLayout(dialog)
        heading = QLabel(f"{APP_NAME} · {__version__}")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        from html import escape

        content.setText(
            f"<h3>Créditos</h3><p>{app_license.CREDITS}</p>"
            f"<pre style='white-space:pre-wrap'>{escape(app_license.LICENSE_TEXT)}</pre>"
            "<p>Quick Mechanic edita archivos locales extraídos del coche. Revisa los cambios y pruébalos en Assetto Corsa.</p>"
        )
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(content, 1)
        link = QLabel(f'<a href="{app_license.LICENSE_URL}">{app_license.LICENSE_URL}</a>')
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _set_startup_option(self, key: str, enabled: bool) -> None:
        try:
            settings.set_value(key, bool(enabled))
        except OSError:
            pass
        if key == "show_guide":
            self._show_guide_on_start = bool(enabled)
        elif key == "show_loading_splash":
            self._show_splash_on_start = bool(enabled)
        label = "Guía de bienvenida" if key == "show_guide" else "Animación de carga"
        self.footer_status.setText(f"{label} al iniciar: {'activada' if enabled else 'desactivada'}")

    def _set_ui_scale(self, factor: float) -> None:
        if factor not in (0.9, 1.0, 1.1, 1.2):
            return
        try:
            settings.set_value("ui_scale", factor)
        except OSError:
            pass
        app = QApplication.instance()
        font = QFont(theme.preferred_font_family())
        font.setPointSizeF(9.0 * factor)
        app.setFont(font)
        self.footer_status.setText(f"Tamaño de interfaz aplicado: {factor * 100:.0f}%")

    def _refresh_footer(self) -> None:
        self._refresh_window_title()
        self._update_dirty_marker()
        car = self._car
        if car is None:
            self.footer_status.setText(
                "Selecciona un coche con carpeta data/ para empezar a tunear."
            )
            self.save_button.setEnabled(False)
            self.revert_button.setEnabled(False)
            self.save_button.setText("Guardar todo")
            self._refresh_utility_buttons()
            return
        pending = car.dirty_files()
        if pending:
            self.footer_status.setText(
                f"{len(pending)} fichero" + ("s" if len(pending) != 1 else "")
                + " con cambios sin guardar: " + ", ".join(pending)
            )
        else:
            self.footer_status.setText(f"{car.ui_name} · sin cambios pendientes")
        self.save_button.setText(f"Guardar ({len(pending)})" if pending else "Guardar todo")
        self.save_button.setEnabled(bool(pending))
        self.revert_button.setEnabled(bool(pending))
        self._refresh_utility_buttons()

    def _save(self) -> None:
        car = self._car
        if car is None or not car.changed:
            return
        baseline = self._history[0] if self._history else None
        try:
            saved = car.save()
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))
            return
        self._record_changes(baseline, car)
        self.info_tab.load(car, self._source.status if self._source else "", self._meta(self._source))
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab):
            tab.load(car)
        self.lab_tab.load(car)
        self._update_car_header()
        self.dashboard_tab.load(car)
        self._refresh_footer()
        self._reset_history()
        self.footer_status.setText(
            f"Guardado a las {time.strftime('%H:%M')}: " + ", ".join(saved)
            + "   ·   respaldo completo y .bak conservados"
        )

    def _record_changes(self, baseline: dict | None, car) -> None:
        """Anota en el historial que parametros han cambiado de la version de partida."""
        if not isinstance(baseline, dict):
            return
        try:
            changes = garage.changes_between(baseline, car.setup_snapshot())
            if changes:
                garage.record_changes(car.name, changes)
        except (garage.GarageError, OSError, ValueError):
            pass

    def _reload_all_views(self) -> None:
        """Recarga todas las vistas tras restaurar un setup o un fichero suelto."""
        car = self._car
        if car is None:
            return
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab, self.lab_tab):
            tab.load(car)
        self.dashboard_tab.load(car)
        self.info_tab.load(car, self._source.status if self._source else "", self._meta(self._source))
        self._update_car_header()
        self._on_editor_changed()

    def _reload_current(self) -> None:
        if self._source is None or self._car is None:
            return
        if self._car.changed and not self._confirm_discard():
            return
        self._load_car(self._source, car_data.CarData.from_car(self._source))
        self.footer_status.setText(f"{self._source.ui_name} · recargado desde disco")

    def _run_car_repair(self) -> None:
        """Revisa car.ini/aero.ini; la reparacion exige confirmacion y deja copias .bak."""
        if self._source is None or self._car is None:
            return
        if self._car.changed and not self._confirm_discard():
            return
        try:
            issues = car_repair.diagnose(self._source.folder)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "No se pudo revisar el coche", str(error))
            return
        if not issues:
            QMessageBox.information(self, "Datos correctos", "No se ha encontrado ningún problema en los datos de este coche.")
            return
        listing = "\n".join(f"• {issue.title}: {issue.detail}" for issue in issues)
        answer = QMessageBox.question(
            self,
            "Reparar datos del coche",
            f"Se han encontrado estos problemas:\n\n{listing}\n\n"
            "Antes de cambiar nada se guardará una copia .bak de cada archivo afectado. ¿Reparar ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = car_repair.repair(self._source.folder, confirmed=True)
        except (OSError, ValueError, PermissionError) as error:
            QMessageBox.critical(self, "No se pudo reparar el coche", str(error))
            return
        try:
            reloaded = car_data.CarData.from_car(self._source) if self._source.editable else None
        except Exception as error:  # datos reparados pero ilegibles: no cerrar la app
            QMessageBox.critical(self, "No se pudo recargar el coche", str(error))
            self._load_car(None, None)
            return
        self._load_car(self._source, reloaded)
        self._refresh_home()
        self._update_dirty_marker()
        changed = ", ".join(result.changed_files) or "ninguno"
        remaining = f"\nAvisos que quedan sin reparar: {len(result.remaining)}." if result.remaining else ""
        QMessageBox.information(self, "Reparación completada", f"Archivos modificados: {changed}.{remaining}")

    def _confirm_discard(self) -> bool:
        """True si se puede continuar (guardando o descartando)."""
        if self._car is None:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Cambios sin guardar")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            f"Hay cambios sin guardar en {self._car.ui_name}: "
            + ", ".join(self._car.dirty_files())
        )
        save = box.addButton("Guardar", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Descartar", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            self._save()
            return self._car is None or not self._car.changed
        return clicked is discard

    def _choose_ac_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Elige la carpeta de Assetto Corsa (la que contiene content/cars)"
        )
        if not folder:
            return
        candidate = Path(folder)
        if not (candidate / "content" / "cars").is_dir():
            QMessageBox.warning(
                self,
                "Carpeta incorrecta",
                "Esa carpeta no contiene content/cars. Elige la carpeta principal "
                "(la que tiene acs.exe).",
            )
            return
        self.ac_root = candidate
        try:
            settings.set_value("ac_root", str(candidate))
        except OSError:
            pass
        self._refresh_tracks()
        self._reload_cars()

    def _open_data_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elige la carpeta data del coche")
        if not folder:
            return
        path = Path(folder)
        if not (path / "engine.ini").is_file():
            QMessageBox.warning(
                self,
                "No parece una carpeta data",
                "Dentro no hay engine.ini. Elige la carpeta 'data' del coche.",
            )
            return
        car = ac_scanner.Car.from_data_dir(path)
        car.ui_name = f"{car.ui_name}   [carpeta externa]"
        self._extra_cars = [car] + [c for c in self._extra_cars if c.folder != car.folder]
        self._meta_cache.pop(car.folder, None)
        self._index_car_search_terms()
        self.search.clear()
        self._apply_filter()
        for row, candidate in enumerate(self._shown):
            if candidate.folder == car.folder:
                self.car_list.setCurrentRow(row)
                break

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (API de Qt)
        if self._car is not None and self._car.changed and not self._confirm_discard():
            self._exit_requested = False
            event.ignore()
            return
        try:
            saved_settings = settings.load()
            saved_settings.update({
                "window_geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                "window_state": bytes(self.saveState().toBase64()).decode("ascii"),
                "splitter_sizes": self._splitter.sizes(),
                "last_tab": self.tabs.currentIndex(),
            })
            settings.save(saved_settings)
        except OSError:
            pass
        if self._close_to_tray and self._tray is not None and not self._exit_requested:
            self.hide()
            event.ignore()
            return
        busy = any(t is not None and t.isRunning() for t in (self._scan_thread, self._load_thread))
        if busy:
            self._exit_requested = True
            self.hide()
            event.ignore()
            return
        if self._tray is not None:
            self._tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(True)
        event.accept()


def relaunch_command(argv: list[str] | None = None) -> tuple[str, list[str]]:
    """Programa y argumentos para volver a abrir la app tal y como se abrio."""
    source = list(sys.argv[1:] if argv is None else argv)
    extra = [
        argument for argument in source if argument not in ("--selftest", "--background")
    ]
    if getattr(sys, "frozen", False):
        return sys.executable, extra
    launcher = Path(__file__).resolve().parent.parent / "launcher.py"
    prefix = [str(launcher)] if launcher.is_file() else ["-m", "quickmechanic"]
    return sys.executable, prefix + extra


def restart_application() -> bool:
    """Relanza la app con los mismos argumentos (para aplicar el idioma).

    Devuelve ``True`` si el nuevo proceso arrancó; la ventana actual se cierra
    desde quien llama para no dejar dos instancias abiertas.
    """
    from PyQt6.QtCore import QProcess

    program, arguments = relaunch_command()
    started = QProcess.startDetached(program, arguments)
    if started:
        app = QApplication.instance()
        if app is not None:
            app.quit()
    return bool(started)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="QuickMechanic", description="Editor de coches de Assetto Corsa"
    )
    parser.add_argument("--ac-root", help="ruta de la instalacion de Assetto Corsa")
    parser.add_argument("--background", action="store_true", help="inicia minimizada/en bandeja (uso del inicio de Windows)")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="comprueba la instalacion y el ciclo de edicion sin abrir la ventana",
    )
    parser.add_argument("--report", help="escribe el informe del --selftest en un fichero")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.selftest:
        from .selftest import run

        return run(ac_root=args.ac_root, report=args.report)

    i18n.set_language(i18n.load_saved_language())
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    theme.apply(app)
    # La membresía se comprueba en el servidor antes de abrir ninguna función protegida.
    monitor = AccessMonitor(app)
    if not AccessGate(monitor).run():
        return 0
    window = MainWindow(ac_root=args.ac_root, background=args.background, access_monitor=monitor)
    if args.background and window._tray is not None:
        window.hide()
    elif args.background:
        window.showMinimized()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
