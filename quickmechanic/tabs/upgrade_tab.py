"""Pestaña Mejoras: stage tuning, RTO, ficha ui_car.json, biblioteca y respaldos."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QMessageBox as _QtMessageBox, QVBoxLayout

from .. import settings, widgets
from ..component_library import ComponentLibrary
from ..qt_i18n import (
    QComboBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QWidget,
)
from ..rto import RTOParser
from ..stage_tuner import StageTuner
from ..ui_car import UIManager

if TYPE_CHECKING:
    from ..ac_scanner import Car

_YES = _QtMessageBox.StandardButton.Yes


def _page(parent_layout_spacing: int = 12) -> tuple[QWidget, QVBoxLayout]:
    """Página con márgenes y separación uniformes para todas las subpestañas."""
    page = QWidget()
    box = QVBoxLayout(page)
    box.setContentsMargins(12, 12, 12, 12)
    box.setSpacing(parent_layout_spacing)
    return page, box


class UpgradeTab(QWidget):
    """Mejoras del coche: se aplican sobre data/ y ui/ y piden confirmación antes de escribir."""

    carChanged = pyqtSignal()
    statusMessage = pyqtSignal(str)

    def __init__(self, is_dirty: Callable[[], bool], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_dirty = is_dirty
        self._car_dir: Optional[Path] = None
        self._rto: Optional[RTOParser] = None
        self._rto_dirty = False
        self._rto_index = 0
        lib_path = settings.settings_path().parent / "component_library.json"
        lib_path.parent.mkdir(parents=True, exist_ok=True)
        self._library = ComponentLibrary(str(lib_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.car_label = QLabel("")
        self.car_label.setObjectName("pageDescription")
        layout.addWidget(self.car_label)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_stage(), "Stage tuning")
        self.tabs.addTab(self._build_rto(), "RTO")
        self.tabs.addTab(self._build_ficha(), "Ficha ui_car")
        self.tabs.addTab(self._build_library(), "Biblioteca")
        self.tabs.addTab(self._build_backups(), "Respaldos")
        layout.addWidget(self.tabs)
        self._refresh()

    # ----- construcción -------------------------------------------------
    def _build_stage(self) -> QWidget:
        page, box = _page()
        self.stage_label = QLabel("")
        self.stage_label.setObjectName("pageDescription")
        box.addWidget(self.stage_label)

        profiles = widgets.Panel("Perfiles de mejora")
        profiles.add_note("Aplica un perfil de mejora. Se modifican los ficheros del coche.")
        self.stage_buttons: list[QPushButton] = []
        self.stage_descriptions: list[QLabel] = []
        for stage in (1, 2, 3):
            row = QWidget()
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(0, 0, 0, 0)
            row_box.setSpacing(12)
            button = QPushButton(f"Stage {stage}")
            button.setMinimumWidth(120)
            button.clicked.connect(lambda _checked=False, n=stage: self._apply_stage(n))
            description = QLabel("")
            description.setWordWrap(True)
            description.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            row_box.addWidget(button)
            row_box.addWidget(description, 1)
            profiles.add_widget(row)
            self.stage_buttons.append(button)
            self.stage_descriptions.append(description)
        box.addWidget(profiles)

        reset = widgets.Panel("Stock")
        reset.add_note("Restaura la configuración de fábrica. Se modifican los ficheros del coche.")
        self.stage_reset = QPushButton("Volver a stock")
        self.stage_reset.clicked.connect(self._reset_stock)
        reset.add_widget(self.stage_reset)
        box.addWidget(reset)
        box.addStretch(1)
        return page

    def _build_rto(self) -> QWidget:
        page, box = _page()
        panel = widgets.Panel("Relaciones de transmisión")
        picker = QHBoxLayout()
        self.rto_file = QComboBox()
        self.rto_file.addItems(["final.rto", "ratios.rto"])
        self.rto_file.currentIndexChanged.connect(self._rto_change_file)
        picker.addWidget(self.rto_file)
        picker.addStretch(1)
        panel.layout_box().addLayout(picker)
        self.rto_list = QListWidget()
        panel.add_widget(self.rto_list)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        for text, slot in (
            ("Añadir", self._rto_add),
            ("Quitar", self._rto_remove),
            ("Ordenar", self._rto_sort),
            ("Guardar", self._rto_save),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            bar.addWidget(button)
        panel.layout_box().addLayout(bar)
        box.addWidget(panel)
        return page

    def _build_ficha(self) -> QWidget:
        page, box = _page()
        panel = widgets.Panel("Datos del coche (ui_car.json)")
        self._ficha: dict[str, QLineEdit] = {}
        for key, label in (
            ("name", "Nombre"),
            ("brand", "Marca"),
            ("class", "Clase"),
            ("country", "País"),
            ("author", "Autor"),
            ("version", "Versión"),
            ("tags", "Tags (separados por coma)"),
            ("description", "Descripción"),
        ):
            edit = QLineEdit()
            self._ficha[key] = edit
            panel.add(label, edit)
        self._ficha_year = QSpinBox()
        self._ficha_year.setRange(1886, 2100)
        panel.add("Año", self._ficha_year)
        box.addWidget(panel)
        save = QPushButton("Guardar ficha")
        save.clicked.connect(self._ficha_save)
        box.addWidget(save, 0, Qt.AlignmentFlag.AlignLeft)
        box.addStretch(1)
        return page

    def _build_library(self) -> QWidget:
        page, box = _page()
        panel = widgets.Panel("Componentes guardados")
        self.lib_type = QComboBox()
        self.lib_type.addItems(ComponentLibrary.COMPONENT_TYPES)
        self.lib_type.currentIndexChanged.connect(self._library_show)
        panel.add("Tipo", self.lib_type)
        self.lib_list = QListWidget()
        panel.add_widget(self.lib_list)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        for text, slot in (
            ("Eliminar", self._library_delete),
            ("Importar…", self._library_import),
            ("Exportar todo…", self._library_export),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            bar.addWidget(button)
        panel.layout_box().addLayout(bar)
        box.addWidget(panel)
        box.addStretch(1)
        return page

    def _build_backups(self) -> QWidget:
        page, box = _page()
        panel = widgets.Panel("Copias de seguridad")
        panel.add_note(
            "Restaura las copias .bak que se crean al guardar (data/ y ui/). "
            "Vuelve a la última versión guardada antes de cada cambio."
        )
        restore = QPushButton("Restaurar copias .bak")
        restore.clicked.connect(self._restore_backups)
        panel.add_widget(restore)
        box.addWidget(panel)
        box.addStretch(1)
        return page

    # ----- estado -------------------------------------------------------
    def load(self, source: Optional["Car"]) -> None:
        self._car_dir = Path(source.folder) if source is not None else None
        self._refresh()

    def _data_dir(self) -> Optional[Path]:
        if self._car_dir is None:
            return None
        data = self._car_dir / "data"
        return data if data.is_dir() else None

    def _tuner(self) -> Optional[StageTuner]:
        data = self._data_dir()
        if data is None:
            return None
        try:
            return StageTuner(str(data))
        except Exception as exc:  # noqa: BLE001 - mostrar el error al usuario
            self.statusMessage.emit(f"No se pudo leer el stage: {exc}")
            return None

    def _refresh(self) -> None:
        if self._car_dir is None:
            self.car_label.setText("Selecciona un coche para usar estas mejoras.")
        else:
            self.car_label.setText(f"Coche: {self._car_dir.name}")
        tuner = self._tuner()
        for button in (*self.stage_buttons, self.stage_reset):
            button.setEnabled(tuner is not None)
        if tuner is None:
            text = "Este coche no tiene carpeta data/. Si tiene data.acd se extrae al seleccionarlo."
            self.stage_label.setText(text if self._car_dir is not None else "")
            for description in self.stage_descriptions:
                description.setText("")
        else:
            stage = tuner.get_current_stage()
            self.stage_label.setText(f"Stage actual: {'stock' if not stage else stage}")
            for stage_number, button, description in zip((1, 2, 3), self.stage_buttons, self.stage_descriptions):
                info = tuner.get_stage_description(stage_number)
                button.setToolTip(f"{info.get('title', '')}\n{info.get('description', '')}")
                description.setText(str(info.get("description", "")))
        self._rto_load()
        self._ficha_show()
        self._library_show()

    def _after_write(self, ok: bool, message: str) -> None:
        self.statusMessage.emit(message)
        if ok:
            self.carChanged.emit()
            self._refresh()

    def _warn_dirty(self) -> None:
        QMessageBox.information(
            self, "Cambios sin guardar", "Guarda o descarta los cambios del coche antes de aplicar una mejora."
        )

    # ----- stage tuning -------------------------------------------------
    def _apply_stage(self, stage: int) -> None:
        if self._is_dirty():
            self._warn_dirty()
            return
        tuner = self._tuner()
        if tuner is None:
            return
        info = tuner.get_stage_description(stage)
        title = info.get("title", f"Stage {stage}")
        answer = QMessageBox.question(
            self, "Aplicar stage", f"¿Aplicar {title}? Se modificarán los ficheros del coche."
        )
        if answer != _YES:
            return
        apply = {1: tuner.apply_stage_1, 2: tuner.apply_stage_2, 3: tuner.apply_stage_3}[stage]
        ok = bool(apply())
        self._after_write(ok, f"Stage {stage} aplicado" if ok else "No se pudo aplicar el stage")

    def _reset_stock(self) -> None:
        if self._is_dirty():
            self._warn_dirty()
            return
        tuner = self._tuner()
        if tuner is None:
            return
        answer = QMessageBox.question(self, "Volver a stock", "¿Restaurar la configuración de fábrica del coche?")
        if answer != _YES:
            return
        ok = bool(tuner.reset_to_stock())
        self._after_write(ok, "Coche restaurado a stock" if ok else "No se pudo restaurar el stock")

    # ----- RTO ----------------------------------------------------------
    def _rto_change_file(self, index: int) -> None:
        if self._rto_dirty:
            answer = QMessageBox.question(
                self, "RTO sin guardar", "¿Descartar los cambios sin guardar del RTO?"
            )
            if answer != _YES:
                self.rto_file.blockSignals(True)
                self.rto_file.setCurrentIndex(self._rto_index)
                self.rto_file.blockSignals(False)
                return
        self._rto_index = index
        self._rto_load()

    def _rto_load(self) -> None:
        self._rto = None
        self._rto_dirty = False
        self.rto_list.clear()
        data = self._data_dir()
        if data is None:
            return
        path = data / self.rto_file.currentText()
        if not path.is_file():
            self.rto_list.addItem("Este coche no tiene este fichero RTO.")
            return
        try:
            parser = RTOParser(str(path))
            parser.load()
        except Exception as exc:  # noqa: BLE001
            self.rto_list.addItem(f"No se pudo leer el RTO: {exc}")
            return
        self._rto = parser
        self._rto_show()

    def _rto_show(self) -> None:
        self.rto_list.clear()
        if self._rto is None:
            return
        for index, ratio in enumerate(self._rto.get_ratios()):
            self.rto_list.addItem(f"{index + 1}:  {ratio:.3f}")

    def _rto_add(self) -> None:
        if self._rto is None:
            return
        value, ok = QInputDialog.getDouble(self, "Añadir relación", "Relación (ej. 3.250):", 3.0, 0.1, 30.0, 3)
        if ok:
            self._rto.add_ratio(value)
            self._rto_dirty = True
            self._rto_show()

    def _rto_remove(self) -> None:
        row = self.rto_list.currentRow()
        if self._rto is None or row < 0:
            return
        self._rto.remove_ratio(row)
        self._rto_dirty = True
        self._rto_show()

    def _rto_sort(self) -> None:
        if self._rto is None:
            return
        self._rto.sort_ratios()
        self._rto_dirty = True
        self._rto_show()

    def _rto_save(self) -> None:
        if self._rto is None or not self._rto_dirty:
            return
        try:
            self._rto.save()
        except Exception as exc:  # noqa: BLE001
            self.statusMessage.emit(f"No se pudo guardar el RTO: {exc}")
            return
        self._rto_dirty = False
        self._after_write(True, f"{self.rto_file.currentText()} guardado")

    # ----- ficha ui_car.json --------------------------------------------
    def _ficha_show(self) -> None:
        enabled = self._car_dir is not None
        for edit in self._ficha.values():
            edit.setEnabled(enabled)
        self._ficha_year.setEnabled(enabled)
        if not enabled:
            return
        ui = UIManager(str(self._car_dir))
        if not ui.load():
            return
        self._ficha["name"].setText(ui.get_name())
        self._ficha["brand"].setText(ui.get_brand())
        self._ficha["class"].setText(ui.get_class())
        self._ficha["country"].setText(ui.get_country())
        self._ficha["author"].setText(ui.get_author())
        self._ficha["version"].setText(ui.get_version())
        self._ficha["tags"].setText(", ".join(ui.get_tags()))
        self._ficha["description"].setText(ui.get_description())
        self._ficha_year.setValue(ui.get_year() or 2000)

    def _ficha_save(self) -> None:
        if self._car_dir is None:
            return
        ui = UIManager(str(self._car_dir))
        if not ui.load():
            self.statusMessage.emit("Este coche no tiene ui/ui_car.json")
            return
        ui.set_name(self._ficha["name"].text().strip())
        ui.set_brand(self._ficha["brand"].text().strip())
        ui.set_class(self._ficha["class"].text().strip())
        ui.set_country(self._ficha["country"].text().strip())
        ui.set_author(self._ficha["author"].text().strip())
        ui.set_version(self._ficha["version"].text().strip())
        ui.set_tags([tag.strip() for tag in self._ficha["tags"].text().split(",") if tag.strip()])
        ui.set_description(self._ficha["description"].text().strip())
        ui.set_year(self._ficha_year.value())
        ok = bool(ui.save(backup=True))
        self._after_write(ok, "Ficha guardada" if ok else "No se pudo guardar la ficha")

    # ----- biblioteca ---------------------------------------------------
    def _library_show(self) -> None:
        self.lib_list.clear()
        for component in self._library.get_components(self.lib_type.currentText()):
            self.lib_list.addItem(str(component.get("name") or component.get("id") or "(sin nombre)"))

    def _library_delete(self) -> None:
        row = self.lib_list.currentRow()
        kind = self.lib_type.currentText()
        components = self._library.get_components(kind)
        if row < 0 or row >= len(components):
            return
        component_id = components[row].get("id")
        if component_id is None:
            return
        self._library.delete_component(kind, component_id)
        self._library.save()
        self._library_show()

    def _library_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar componentes", "", "JSON (*.json)")
        if path and self._library.import_components(path):
            self._library.save()
            self._library_show()
            self.statusMessage.emit("Componentes importados")

    def _library_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar componentes", "componentes.json", "JSON (*.json)")
        if path and self._library.export_all_components(path):
            self.statusMessage.emit("Biblioteca exportada")

    # ----- respaldos ----------------------------------------------------
    def _restore_backups(self) -> None:
        if self._is_dirty():
            self._warn_dirty()
            return
        if self._car_dir is None:
            return
        baks = []
        for folder in (self._car_dir / "data", self._car_dir / "ui"):
            if folder.is_dir():
                baks.extend(folder.glob("*.bak"))
        if not baks:
            self.statusMessage.emit("No hay copias .bak para restaurar")
            return
        answer = QMessageBox.question(self, "Restaurar", f"¿Restaurar {len(baks)} copia(s) .bak?")
        if answer != _YES:
            return
        restored = 0
        for bak in baks:
            original = bak.with_name(bak.name[:-4])
            try:
                shutil.copy2(bak, original)
                os.remove(bak)
                restored += 1
            except OSError as exc:
                self.statusMessage.emit(f"Error restaurando {bak.name}: {exc}")
        self._after_write(restored > 0, f"{restored} fichero(s) restaurados")
