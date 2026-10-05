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
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QObject,
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

from .qt_i18n import QAction, QDialog, QFileDialog, QFrame, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QTabWidget, QWidget

from . import (
    APP_NAME,
    __version__,
    ac_scanner,
    car_data,
    content_manager,
    drift,
    i18n,
    license as app_license,
    presets,
    settings,
    skins,
    swaps,
    theme,
    updates,
    widgets,
)
from .branding import LoadingSplash, app_icon
from .cm_panel import ContentManagerPanel
from .guide import DISCORD_URL, QuickGuideDialog
from .tabs import AidsTab, AdvancedTab, ChassisTab, DashboardTab, GearboxTab, InfoTab, MotorTab

SIDEBAR_MIN_WIDTH = 300
SIDEBAR_MAX_WIDTH = 380
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


class MainWindow(QMainWindow):
    def __init__(
        self,
        ac_root: str | Path | None = None,
        extra_cars: list[ac_scanner.Car] | None = None,
        background: bool = False,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  ·  VEHICLE ENGINEERING")
        self.setWindowIcon(app_icon())
        self.resize(1520, 940)
        self.setMinimumSize(1180, 740)
        self._animations: list[QPropertyAnimation] = []
        self._background_start = background
        self._tray: QSystemTrayIcon | None = None
        self._close_to_tray = bool(settings.get("close_to_tray", sys.platform == "win32"))
        self._exit_requested = False
        self._scan_thread: QThread | None = None
        self._scan_worker: _LibraryScanWorker | None = None
        self._update_thread: QThread | None = None
        self._update_worker: updates.UpdateWorker | None = None
        self._download_thread: QThread | None = None
        self._update_info: updates.UpdateInfo | None = None
        self._skipped_update = str(settings.get("skipped_update", "") or "")
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
        self._restore_window_state()
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

        self.update_notification = updates.UpdateNotice()
        self.update_notification.downloadRequested.connect(self._start_update_download)
        self.update_notification.openPageRequested.connect(self._open_update_page)
        self.update_notification.dismissed.connect(self._dismiss_update_notice)
        outer.addWidget(self.update_notification, 0)

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
        self.aids_tab = AidsTab()
        self.advanced_tab = AdvancedTab()
        self.tabs.addTab(self.dashboard_tab, "Resumen")
        self.tabs.addTab(self.motor_tab, "Motor")
        self.tabs.addTab(self.gear_tab, "Caja de cambios")
        self.tabs.addTab(self.chassis_tab, "Chasis")
        self.tabs.addTab(self.info_tab, "Diagnostico")
        self.tabs.addTab(self.aids_tab, "Asistencias")
        self.tabs.addTab(self.advanced_tab, "Avanzado")
        for index, tip in enumerate((
            "Resumen de rendimiento y estadisticas de la biblioteca",
            "Curvas de potencia y par, limitador y turbo",
            "Editor de relaciones, diferencial y velocidades",
            "Suspension, geometria, frenos y neumaticos",
            "Ficha tecnica, estado de archivos y diagnostico",
            "Compatibilidad y controles de ABS y traccion",
            "Editor experto de parametros numericos existentes en archivos locales",
        )):
            self.tabs.setTabToolTip(index, tip)
        self.tabs.tabBar().hide()
        self.page_eyebrow = QLabel("01  /  PERFORMANCE OVERVIEW")
        self.page_eyebrow.setObjectName("pageEyebrow")
        self.page_title = QLabel("Resumen")
        self.page_title.setObjectName("pageTitle")
        self.page_description = QLabel("Estado de la colección y cálculos derivados de los archivos del coche.")
        self.page_description.setWordWrap(True)
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
        nav.setFixedWidth(168)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(8, 10, 8, 10)
        nav_layout.setSpacing(5)
        nav_label = QLabel("GARAGE")
        nav_label.setObjectName("dashboardHeading")
        nav_layout.addWidget(nav_label)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        nav_items = (("◈", "Resumen", 0), ("⌁", "Motor", 1), ("⚙", "Caja cambios", 2),
                     ("◉", "Chasis", 3), ("◌", "Asistencias", 5), ("≋", "Avanzado", 6))
        for icon, label, index in nav_items:
            button = QPushButton(f"{icon}    {label}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setToolTip(self.tabs.tabToolTip(index))
            button.clicked.connect(lambda _checked=False, page=index: self.tabs.setCurrentIndex(page))
            self.nav_group.addButton(button, index)
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
        nav_layout.addStretch(1)
        diag = QPushButton("ⓘ    Diagnostico")
        diag.setObjectName("navButton")
        diag.setCheckable(True)
        diag.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        self.nav_group.addButton(diag, 4)
        nav_layout.addWidget(diag)
        self.nav_buttons.append(diag)
        self.tabs.currentChanged.connect(self._sync_nav_selection)
        self.nav_group.button(0).setChecked(True)

        self.nav_group.buttonClicked.connect(lambda _button: self._nav_transition())
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab):
            tab.changed.connect(self._on_editor_changed)
        workspace_layout.addWidget(nav, 0)
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
        splitter.setSizes(saved_sizes if isinstance(saved_sizes, list) and len(saved_sizes) == 2 else [330, 1000])
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
        self.export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self, self._export_library_csv)
        self.export_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._refresh_utility_buttons()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(66)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)
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
        titles.addWidget(title)
        titles.addWidget(subtitle)
        layout.addLayout(titles, 0)

        layout.addStretch(1)

        self.path_label = QLabel("")
        self.path_label.setObjectName("headerNote")
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
            button.setMinimumWidth(76)
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
        layout.setContentsMargins(14, 10, 14, 11)
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
        footer.setFixedHeight(58)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        self.footer_status = QLabel("")
        self.footer_status.setObjectName("footerStatus")
        layout.addWidget(self.footer_status, 1)

        self.revert_button = QPushButton("Descartar cambios")
        self.revert_button.setObjectName("danger")
        self.revert_button.setToolTip("Vuelve a leer los .ini del coche y tira los cambios en memoria")
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
            "Escribe solo las lineas cambiadas; antes crea un ZIP de seguridad y conserva el .bak original"
        )
        self.save_button.clicked.connect(self._save)
        layout.addWidget(self.save_button)
        return footer

    # ----------------------------------------------------------- lista de coches
    def _reload_cars(self) -> None:
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
        self._apply_filter()
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

    # ------------------------------------------------------- idioma y actualizaciones
    def _schedule_startup_notices(self) -> None:
        if self._background_start:
            return
        QTimer.singleShot(250, self._show_discord_notification)
        QTimer.singleShot(1200, self._check_updates)

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

    def _check_updates(self, force: bool = False) -> None:
        """Mira si hay una release mas nueva; nunca lanza errores al usuario."""
        if self._background_start and not force:
            return
        if not force and not bool(settings.get("check_updates", True)):
            return
        if self._update_thread is not None and self._update_thread.isRunning():
            return
        self._update_check_forced = bool(force)
        if force:
            self.footer_status.setText("Comprobando actualizaciones en GitHub…")
        worker = updates.UpdateWorker(__version__)
        worker.finished.connect(self._on_update_checked)
        worker.finished.connect(lambda info, check=force: self._report_update_check(info, check))
        worker.failed.connect(self._on_update_failed)
        self._update_worker = worker
        thread = updates.start_worker(worker, self)
        self._update_thread = thread
        thread.finished.connect(lambda ended=thread: self._clear_workers(ended))

    def _on_update_checked(self, info) -> None:
        if info is None or info.tag == self._skipped_update:
            return
        self._update_info = info
        self.update_notification.show_available(info)
        self.footer_status.setText(f"Nueva versión disponible: {info.name or info.tag}")

    def _report_update_check(self, info, forced: bool) -> None:
        if not forced:
            return
        if info is None:
            self.footer_status.setText(
                "No hay versiones nuevas (o no se pudo consultar GitHub en este momento)"
            )
            return
        self.update_notification.show_available(info)
        QMessageBox.information(
            self, "Actualización disponible",
            f"Hay una versión nueva: {info.name or info.tag}.\n\n"
            "Puedes descargarla desde el aviso de la parte superior.",
        )

    def _on_update_failed(self, message: str) -> None:
        # En el arranque se ignora en silencio; si la comprobacion fue a mano, se avisa.
        if not getattr(self, "_update_check_forced", False):
            return
        self.footer_status.setText(f"No se pudo comprobar la versión: {message}")

    def _start_update_download(self) -> None:
        notice = self.update_notification
        if notice.downloaded_path is not None:
            notice.launch_downloaded()
            return
        info = self._update_info or notice.info
        if info is None:
            return
        candidates = updates.asset_candidates(info)
        if not candidates:
            QMessageBox.information(
                self, "Sin instalador en la release",
                "Esta release no trae ningún .exe ni .zip descargable. Ábrela en GitHub "
                "para bajarlo a mano.",
            )
            return
        if self._download_thread is not None and self._download_thread.isRunning():
            return
        notice.show_downloading()
        worker = updates.DownloadWorker(candidates[0])
        worker.finished.connect(self._on_update_downloaded)
        worker.failed.connect(self._on_download_failed)
        thread = updates.start_worker(worker, self)
        self._download_thread = thread
        thread.finished.connect(lambda ended=thread: self._clear_workers(ended))

    def _clear_workers(self, thread: QThread) -> None:
        """Suelta las referencias de un hilo terminado (nunca se usa su objeto C++)."""
        if self._update_thread is thread:
            self._update_thread = None
            self._update_worker = None
        if self._download_thread is thread:
            self._download_thread = None
        if self._exit_requested:
            # Cerrar mientras se descargaba: Qt no admite destruir un hilo vivo.
            QTimer.singleShot(0, self.close)

    def _on_update_downloaded(self, path) -> None:
        self.update_notification.show_downloaded(path)
        self.footer_status.setText(f"Actualización descargada · {path.name}")

    def _on_download_failed(self, message: str) -> None:
        self.update_notification.show_error(message)
        self.footer_status.setText("No se pudo descargar la actualización")

    def _open_update_page(self) -> None:
        info = self._update_info or self.update_notification.info
        url = info.page_url if info is not None else updates.RELEASES_PAGE
        QDesktopServices.openUrl(QUrl(url))

    def _dismiss_update_notice(self) -> None:
        info = self.update_notification.info
        if info is None or self.update_notification.downloaded_path is not None:
            return
        self._skipped_update = info.tag
        try:
            settings.set_value("skipped_update", info.tag)
        except OSError:
            pass

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

    def _nav_transition(self) -> None:
        self._sync_nav_selection(self.tabs.currentIndex())

    def _sync_nav_selection(self, index: int) -> None:
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)
        titles = ("Resumen", "Motor", "Caja de cambios", "Chasis", "Diagnóstico", "Asistencias", "Avanzado")
        eyebrow = ("PERFORMANCE OVERVIEW", "POWERTRAIN LAB", "GEARBOX & RATIOS", "CHASSIS SETUP", "VEHICLE INSPECTION", "DRIVER AIDS", "EXPERT PARAMETERS")
        descriptions = (
            "Estado de la colección y cálculos derivados de los archivos locales del coche.",
            "Lee power.lut y permite editar sus puntos, corte, turbo y entrega de par.",
            "Ajusta relaciones y diferencial; las velocidades teóricas se muestran en una tabla.",
            "Suspensión, geometría, frenos, masa y presiones con análisis instantáneo.",
            "Ficha técnica, alertas de seguridad y estado de los archivos de física.",
            "Inspecciona ABS y control de tracción cuando están declarados por el coche.",
            "Editor experto limitado a parámetros numéricos presentes en los INI abiertos.",
        )
        if 0 <= index < len(titles) and hasattr(self, "page_title"):
            self.page_title.setText(titles[index])
            self.page_eyebrow.setText(f"{index + 1:02d}  /  {eyebrow[index]}")
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
        """Reindexa coches instalados tras operar en Content Manager."""
        if self.ac_root is None:
            self._choose_ac_root()
            return
        self._reload_cars()
        self.footer_status.setText(f"Biblioteca sincronizada · {len(self._cars)} coches revisados")

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

        selected_key = (
            (self._source.name, self._source.folder) if self._source is not None else None
        )
        self.car_list.blockSignals(True)
        self.car_list.clear()
        for car in self._shown:
            favorite = "★  " if car.name in self._favorites else ""
            text = favorite + (car.ui_name if car.editable else f"{car.ui_name}   ·   data.acd")
            item = QListWidgetItem(text)
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

    def _on_car_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_car_keys):
            return
        name, folder = self._visible_car_keys[row]
        source = next((car for car in self._extra_cars + self._cars if car.name == name and car.folder == folder), None)
        if source is None:
            return
        if self._car is not None and self._car.changed and not self._confirm_discard():
            self._reselect(self._source)
            return
        data = car_data.CarData.from_car(source) if source.editable else None
        self._load_car(source, data)

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
        self.info_tab.load(data, source.status if source else "", self._meta(source))

        self.tabs.setTabEnabled(0, True)
        for index in (1, 2, 3, 5, 6):
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
        menu.addSeparator()
        updates_option = menu.addAction("Comprobar actualizaciones al iniciar")
        updates_option.setCheckable(True)
        updates_option.setChecked(bool(settings.get("check_updates", True)))
        updates_option.toggled.connect(self._set_update_check)
        check_now = menu.addAction("Buscar actualizaciones ahora")
        check_now.triggered.connect(lambda: self._check_updates(force=True))
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

    def _set_update_check(self, enabled: bool) -> None:
        try:
            settings.set_value("check_updates", bool(enabled))
        except OSError:
            pass
        if enabled:
            self._check_updates(force=True)
        else:
            self.update_notification.hide()
            self.footer_status.setText("Aviso de actualizaciones desactivado")

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
        try:
            saved = car.save()
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))
            return
        self.info_tab.load(car, self._source.status if self._source else "", self._meta(self._source))
        for tab in (self.motor_tab, self.gear_tab, self.chassis_tab, self.aids_tab, self.advanced_tab):
            tab.load(car)
        self._update_car_header()
        self.dashboard_tab.load(car)
        self._refresh_footer()
        self._reset_history()
        self.footer_status.setText(
            "Guardado: " + ", ".join(saved) + "   ·   respaldo completo y .bak conservados"
        )

    def _reload_current(self) -> None:
        if self._source is None or self._car is None:
            return
        if self._car.changed and not self._confirm_discard():
            return
        self._load_car(self._source, car_data.CarData.from_car(self._source))
        self.footer_status.setText(f"{self._source.ui_name} · recargado desde disco")

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
            })
            settings.save(saved_settings)
        except OSError:
            pass
        if self._close_to_tray and self._tray is not None and not self._exit_requested:
            self.hide()
            event.ignore()
            return
        thread = self._scan_thread
        if thread is not None and thread.isRunning():
            self._exit_requested = True
            self.hide()
            event.ignore()
            return
        for background in (self._update_thread, self._download_thread):
            if background is not None and background.isRunning():
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
    window = MainWindow(ac_root=args.ac_root, background=args.background)
    if args.background and window._tray is not None:
        window.hide()
    elif args.background:
        window.showMinimized()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
