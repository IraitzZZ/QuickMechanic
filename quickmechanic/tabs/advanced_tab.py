"""Editor avanzado de parámetros numéricos existentes en los archivos de física."""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .. import widgets
from ..car_data import AdvancedSetting, CarData


class AdvancedTab(QWidget):
    """Permite editar claves numéricas existentes sin agregar parámetros ficticios."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.car: CarData | None = None
        self._loading = False
        self._rows: list[AdvancedSetting] = []
        self._row_identities: dict[int, AdvancedSetting] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        panel = widgets.Panel("Parámetros numéricos detectados")
        panel.add_note(
            "Editor para usuarios avanzados: muestra valores físicos escalares que ya existen "
            "en los INI abiertos del coche. No crea claves, no modifica data.acd y no aplica "
            "rangos genéricos porque las escalas varían entre mods. Revisa los cambios y prueba en pista.",
            "aviso",
        )
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por archivo, sección o clave…")
        panel.add_widget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setSortingEnabled(False)
        self.table.setHorizontalHeaderLabels(["Archivo", "Sección", "Parámetro", "Valor"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        panel.add_widget(self.table)
        layout.addWidget(panel, 1)
        self.search.textChanged.connect(self._filter)
        self.table.itemChanged.connect(self._value_changed)

    def load(self, car: CarData | None) -> None:
        self.car = car
        self._loading = True
        try:
            self.setEnabled(bool(car and car.editable))
            self._rows = car.advanced_settings() if car and car.editable else []
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(self._rows))
            self._row_identities.clear()
            for row, entry in enumerate(self._rows):
                self._row_identities[row] = entry
                values = (entry.filename, entry.section, entry.key, f"{entry.value:.8g}")
                for column, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    if column != 3:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, column, item)
            self._filter(self.search.text())
        finally:
            self._loading = False

    def _filter(self, text: str) -> None:
        query = text.strip().casefold()
        for row in range(self.table.rowCount()):
            haystack = " ".join(
                self.table.item(row, column).text()
                for column in range(3) if self.table.item(row, column) is not None
            ).casefold()
            self.table.setRowHidden(row, bool(query and query not in haystack))

    def _value_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != 3 or self.car is None:
            return
        entry = self._row_identities.get(item.row())
        if entry is None:
            return
        try:
            value = float(item.text().replace(",", "."))
        except ValueError:
            self._restore_cell(item, entry.value)
            return
        if not math.isfinite(value) or abs(value) > 1e12 or not self.car.set_advanced_value(
            entry.filename, entry.section, entry.key, value
        ):
            self._restore_cell(item, entry.value)
            return
        self._row_identities[item.row()] = AdvancedSetting(entry.filename, entry.section, entry.key, value)
        self._rows = [self._row_identities[row] for row in sorted(self._row_identities)]
        self.changed.emit()

    def _restore_cell(self, item: QTableWidgetItem, value: float) -> None:
        self._loading = True
        item.setText(f"{value:.8g}")
        self._loading = False
