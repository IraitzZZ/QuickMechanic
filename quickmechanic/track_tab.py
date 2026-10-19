"""Explora circuitos y permite ajustar valores numéricos existentes con respaldo."""
from __future__ import annotations

import hashlib
import html
import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)
from . import tracks, theme
from .qt_i18n import QLabel, QLineEdit, QListWidget, QPushButton, QWidget


class TrackTab(QWidget):
    """Explorador de pistas y layouts con lectura segura de metadatos e INI."""

    openRequested = pyqtSignal(str)
    openIniRequested = pyqtSignal(str)
    statusMessage = pyqtSignal(str)
    trackRefreshRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracks: list[tracks.TrackInfo] = []
        self._visible_tracks: list[tracks.TrackInfo] = []
        self._selected: tracks.TrackInfo | None = None
        self._selected_layout = ""
        self._selected_ini = ""
        self._pending_selection = ""
        self._ini_entries: list[tracks.IniEntry] = []
        self._ini_sha256 = ""
        self._ini_original_value = 0.0
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._filter_tracks)
        self._ini_filter_timer = QTimer(self)
        self._ini_filter_timer.setSingleShot(True)
        self._ini_filter_timer.setInterval(140)
        self._ini_filter_timer.timeout.connect(self._filter_ini)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        heading = QLabel("CIRCUITOS INSTALADOS · INSPECCIÓN Y EDICIÓN SEGURA CON RESPALDO")
        heading.setObjectName("sectionLabel")
        outer.addWidget(heading)
        header_row = QHBoxLayout()
        self.refresh_button = QPushButton("Actualizar circuitos")
        self.refresh_button.setObjectName("ghost")
        self.refresh_button.clicked.connect(self.trackRefreshRequested.emit)
        header_row.addStretch(1)
        header_row.addWidget(self.refresh_button)
        outer.addLayout(header_row)
        self.track_filter = QLineEdit()
        self.track_filter.setPlaceholderText("Buscar circuito, layout, país o autor…")
        self.track_filter.setClearButtonEnabled(True)
        self.track_filter.textChanged.connect(lambda _text: self._filter_timer.start())
        outer.addWidget(self.track_filter)
        description = QLabel(
            "Explora circuitos y layouts. Edita solo valores numéricos ya existentes en INI reconocidos; "
            "se crea un respaldo antes de guardar."
        )
        description.setWordWrap(True)
        outer.addWidget(description)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.track_list = QListWidget()
        self.track_list.currentRowChanged.connect(self._select_track)
        splitter.addWidget(self.track_list)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(6)
        self.track_title = QLabel("Selecciona un circuito")
        self.track_title.setObjectName("pageTitle")
        detail_layout.addWidget(self.track_title)
        self.track_meta = QTextBrowser()
        self.track_meta.setMinimumHeight(105)
        self.track_meta.setMaximumHeight(180)
        detail_layout.addWidget(self.track_meta)

        layout_row = QHBoxLayout()
        layout_row.addWidget(QLabel("Layout:"))
        self.layout_list = QListWidget()
        self.layout_list.setMaximumHeight(112)
        self.layout_list.currentRowChanged.connect(self._select_layout)
        layout_row.addWidget(self.layout_list, 1)
        detail_layout.addLayout(layout_row)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Ficheros INI:"))
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(125)
        self.file_list.currentRowChanged.connect(self._select_ini)
        file_row.addWidget(self.file_list, 1)
        detail_layout.addLayout(file_row)

        filter_row = QHBoxLayout()
        self.ini_filter = QLineEdit()
        self.ini_filter.setPlaceholderText("Buscar en sección, clave o valor…")
        self.ini_filter.setClearButtonEnabled(True)
        self.ini_filter.textChanged.connect(lambda _text: self._ini_filter_timer.start())
        filter_row.addWidget(self.ini_filter, 1)
        self.open_button = QPushButton("Abrir carpeta")
        self.open_button.setObjectName("ghost")
        self.open_button.clicked.connect(self._open_track)
        filter_row.addWidget(self.open_button)
        self.open_ini_button = QPushButton("Abrir INI")
        self.open_ini_button.setObjectName("ghost")
        self.open_ini_button.setToolTip("Abre el INI seleccionado en el editor de texto del sistema; el editor rápido guarda con copia de seguridad.")
        self.open_ini_button.setEnabled(False)
        self.open_ini_button.clicked.connect(self._open_ini)
        filter_row.addWidget(self.open_ini_button)
        detail_layout.addLayout(filter_row)
        edit_row = QHBoxLayout()
        self.section_list = QListWidget()
        self.section_list.setMaximumHeight(92)
        self.section_list.currentRowChanged.connect(self._select_section)
        self.key_list = QListWidget()
        self.key_list.setMaximumHeight(92)
        self.key_list.currentRowChanged.connect(self._select_key)
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setDecimals(6)
        self.value_spin.setRange(-1_000_000_000, 1_000_000_000)
        self.value_spin.setEnabled(False)
        self.save_value_button = QPushButton("Guardar valor")
        self.save_value_button.setObjectName("primary")
        self.save_value_button.setEnabled(False)
        self.save_value_button.clicked.connect(self._save_ini_value)
        self.value_spin.valueChanged.connect(self._update_ini_save_enabled)
        edit_row.addWidget(self.section_list, 1)
        edit_row.addWidget(self.key_list, 1)
        edit_row.addWidget(self.value_spin, 1)
        edit_row.addWidget(self.save_value_button)
        detail_layout.addLayout(edit_row)
        self.ini_view = QTextBrowser()
        self.ini_view.setMinimumHeight(230)
        detail_layout.addWidget(self.ini_view, 1)
        self.status = QLabel("")
        self.status.setObjectName("previewSubtitle")
        detail_layout.addWidget(self.status)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter, 1)

    def _filter_tracks(self) -> None:
        needle = self.track_filter.text().strip().casefold()
        selected_name = self._pending_selection or (self._selected.name if self._selected else "")
        self._pending_selection = ""
        self._visible_tracks = [
            track for track in self._tracks
            if not needle or needle in track.name.casefold()
            or needle in track.display_name.casefold() or needle in track.country.casefold()
            or needle in str(track.metadata.get("author", "")).casefold()
            or any(needle in layout.name.casefold() or needle in layout.display_name.casefold() for layout in track.layouts)
        ]
        self.track_list.blockSignals(True)
        self.track_list.clear()
        for track in self._visible_tracks:
            label = track.display_name
            if track.country:
                label += f"  ·  {track.country}"
            if track.layouts:
                label += f"  ·  {len(track.layouts)} layouts"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, track.name)
            item.setToolTip(str(track.folder))
            self.track_list.addItem(item)
        self.track_list.blockSignals(False)
        row = next((index for index, track in enumerate(self._visible_tracks) if track.name == selected_name), 0 if self._visible_tracks else -1)
        self.track_list.setCurrentRow(row)
        self.status.setText(
            f"{len(self._visible_tracks)} de {len(self._tracks)} circuitos"
            if self._tracks else (self._message or "Sin circuitos instalados")
        )
        if row < 0:
            self._selected = None
            self._clear_details()

    def set_tracks(self, values: list[tracks.TrackInfo], message: str = "") -> None:
        self._pending_selection = self._selected.name if self._selected else ""
        self._tracks = list(values)
        self._message = message
        self._filter_tracks()

    def _clear_details(self) -> None:
        self._selected_layout = ""
        self._selected_ini = ""
        self.track_title.setText("Selecciona un circuito")
        self.track_meta.clear()
        self.layout_list.clear()
        self.file_list.clear()
        self.ini_view.clear()
        self.section_list.clear()
        self.key_list.clear()
        self.open_button.setEnabled(False)
        self.open_ini_button.setEnabled(False)

    def _select_track(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_tracks):
            self._selected = None
            self._clear_details()
            return
        previous = self._selected
        self._selected = self._visible_tracks[row]
        if previous is not None and previous.name != self._selected.name:
            self._selected_layout = ""
            self._selected_ini = ""
        track = self._selected
        self.track_title.setText(track.display_name)
        self.open_button.setEnabled(True)
        fields = [
            ("Carpeta", track.name),
            ("País", track.country or "—"),
            ("Autor", str(track.metadata.get("author", "—"))),
            ("Año", str(track.metadata.get("year", "—"))),
            ("Descripción", str(track.metadata.get("description", "—"))),
            ("Longitud", str(track.metadata.get("length", "—"))),
            ("Pit boxes", str(track.metadata.get("pitboxes", "—"))),
            ("Metadatos", track.metadata_error or (str(track.ui_file.relative_to(track.folder)) if track.ui_file else "ui_track.json no encontrado")),
            ("Modelos", str(len(track.model_files))),
        ]
        self.track_meta.setHtml(
            "<html><body style='font-size:12px;color:" + theme.FG + "'>"
            + "".join(f"<p><b>{html.escape(label)}:</b> {html.escape(value)}</p>" for label, value in fields)
            + "</body></html>"
        )
        self.layout_list.blockSignals(True)
        self.layout_list.clear()
        for layout in track.layouts:
            notes = []
            if layout.data_dir is not None:
                notes.append("data")
            if layout.model_file is not None:
                notes.append("model")
            if layout.ui_file is not None:
                notes.append("UI")
            label = layout.display_name + (f"  ·  {', '.join(notes)}" if notes else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, layout.name)
            self.layout_list.addItem(item)
        self.layout_list.blockSignals(False)
        wanted_layout = next(
            (index for index in range(self.layout_list.count())
             if self.layout_list.item(index).data(Qt.ItemDataRole.UserRole) == self._selected_layout),
            0 if self.layout_list.count() else -1,
        )
        self.layout_list.setCurrentRow(wanted_layout)
        self._fill_ini_files()

    def _select_layout(self, row: int) -> None:
        if row >= 0 and self.layout_list.currentItem() is not None:
            selected = self.layout_list.currentItem().data(Qt.ItemDataRole.UserRole)
            if selected != self._selected_layout:
                self._selected_layout = selected
                self._selected_ini = ""
        self._fill_ini_files()

    def _fill_ini_files(self) -> None:
        self.file_list.blockSignals(True)
        self.file_list.clear()
        track = self._selected
        if track is None:
            self.file_list.blockSignals(False)
            self.ini_view.clear()
            return
        paths = list(track.model_files)
        if track.data_dir is not None:
            paths.extend(track.data_dir.glob("*.ini"))
        layout_name = self.layout_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.layout_list.currentItem() else None
        layout = next((entry for entry in track.layouts if entry.name == layout_name), None)
        if layout is not None and layout.data_dir is not None:
            paths.extend(layout.data_dir.glob("*.ini"))
        unique: dict[str, Path] = {}
        for path in paths:
            try:
                relative = path.relative_to(track.folder)
                paths_to_check = (path, *path.parents)
                if any(candidate.is_symlink() for candidate in paths_to_check if candidate == track.folder or track.folder in candidate.parents):
                    continue
                path.resolve(strict=True).relative_to(track.folder.resolve(strict=True))
                if path.is_file():
                    unique[relative.as_posix()] = path
            except (OSError, ValueError, RuntimeError):
                continue
        for relative, path in sorted(unique.items(), key=lambda pair: pair[0].casefold()):
            item = QListWidgetItem(relative)
            item.setData(Qt.ItemDataRole.UserRole, relative)
            self.file_list.addItem(item)
        self.file_list.blockSignals(False)
        self.open_ini_button.setEnabled(self.file_list.count() > 0)
        if self.file_list.count():
            wanted_file = next(
                (index for index in range(self.file_list.count())
                 if self.file_list.item(index).data(Qt.ItemDataRole.UserRole) == self._selected_ini),
                0,
            )
            self.file_list.setCurrentRow(wanted_file)
        else:
            self._selected_ini = ""
            self.ini_view.clear()
            self.status.setText("No se encontraron INI técnicos en las ubicaciones reconocidas.")

    def _select_ini(self, row: int) -> None:
        if row < 0 or self._selected is None:
            self.ini_view.clear()
            return
        item = self.file_list.item(row)
        relative = item.data(Qt.ItemDataRole.UserRole)
        self._selected_ini = relative
        path = self._selected.folder / relative
        try:
            entries = tracks.read_ini(path, self._selected.folder)
            self._ini_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        except (tracks.TrackError, OSError) as error:
            self.ini_view.setPlainText(str(error))
            self._reset_ini_editor()
            return
        self._ini_entries = entries
        self._populate_ini_editor(entries)
        self._render_entries(entries)

    def _render_entries(self, entries: list[tracks.IniEntry]) -> None:
        needle = self.ini_filter.text().strip().casefold()
        rows = [entry for entry in entries if not needle or needle in entry.section.casefold() or needle in entry.key.casefold() or needle in entry.value.casefold()]
        body = "".join(
            f"<tr><td style='color:{theme.MUTED}'>{html.escape(entry.section)}</td>"
            f"<td style='color:{theme.ACCENT}'>{html.escape(entry.key)}</td>"
            f"<td>{html.escape(entry.value)}</td></tr>"
            for entry in rows[:1500]
        )
        self.ini_view.setHtml(
            f"<html><body style='color:{theme.FG};font-size:12px'>"
            f"<p style='color:{theme.MUTED}'>{len(rows)} claves · solo lectura</p>"
            f"<table cellspacing='0' cellpadding='2'>{body}</table></body></html>"
        )

    def _filter_ini(self) -> None:
        if self._selected is None or self.file_list.currentRow() < 0:
            return
        # Filtra la instantánea ya cargada; no cambia el hash de control si otro
        # programa modifica el INI, así Guardar puede detectar el conflicto.
        self._render_entries(self._ini_entries)

    def _reset_ini_editor(self) -> None:
        self.section_list.clear()
        self.key_list.clear()
        self.value_spin.setEnabled(False)
        self.save_value_button.setEnabled(False)
        self._ini_original_value = 0.0

    def _populate_ini_editor(self, entries: list[tracks.IniEntry]) -> None:
        sections = sorted({entry.section for entry in entries if entry.section}, key=str.casefold)
        self.section_list.blockSignals(True)
        self.section_list.clear()
        self.section_list.addItems(sections)
        self.section_list.blockSignals(False)
        self.section_list.setCurrentRow(0 if sections else -1)
        self._load_keys_for_section()

    def _select_section(self, _row: int) -> None:
        self._load_keys_for_section()

    def _load_keys_for_section(self) -> None:
        section = self.section_list.currentItem().text() if self.section_list.currentItem() else ""
        keys = sorted(
            {entry.key for entry in self._ini_entries if entry.section.casefold() == section.casefold()},
            key=str.casefold,
        )
        self.key_list.blockSignals(True)
        self.key_list.clear()
        self.key_list.addItems(keys)
        self.key_list.blockSignals(False)
        self.key_list.setCurrentRow(0 if keys else -1)
        self._load_numeric_value()

    def _select_key(self, _row: int) -> None:
        self._load_numeric_value()

    def _load_numeric_value(self) -> None:
        section = self.section_list.currentItem().text() if self.section_list.currentItem() else ""
        key = self.key_list.currentItem().text() if self.key_list.currentItem() else ""
        entry = next(
            (item for item in self._ini_entries if item.section.casefold() == section.casefold() and item.key.casefold() == key.casefold()),
            None,
        )
        try:
            if entry is None:
                raise ValueError
            value = float(entry.value)
            if not math.isfinite(value):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            self.value_spin.setEnabled(False)
            self.save_value_button.setEnabled(False)
            return
        self._ini_original_value = value
        self.value_spin.setRange(max(-1_000_000_000.0, value - 1_000_000_000.0), min(1_000_000_000.0, value + 1_000_000_000.0))
        self.value_spin.blockSignals(True)
        self.value_spin.setValue(value)
        self.value_spin.blockSignals(False)
        self.value_spin.setEnabled(True)
        self.save_value_button.setEnabled(False)

    def _update_ini_save_enabled(self, value: float) -> None:
        self.save_value_button.setEnabled(
            self.value_spin.isEnabled() and math.isfinite(value) and value != self._ini_original_value
        )

    def _save_ini_value(self) -> None:
        if self._selected is None or not self._selected_ini:
            return
        section = self.section_list.currentItem().text() if self.section_list.currentItem() else ""
        key = self.key_list.currentItem().text() if self.key_list.currentItem() else ""
        if not section or not key:
            return
        try:
            path = tracks.edit_ini_number(
                self._selected,
                self._selected.folder / self._selected_ini,
                section,
                key,
                self.value_spin.value(),
                self._ini_sha256,
            )
            self._ini_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            self.statusMessage.emit("INI guardado · copia de seguridad creada antes del cambio")
            entries = tracks.read_ini(path, self._selected.folder)
            self._ini_entries = entries
            self._populate_ini_editor(entries)
            self._render_entries(entries)
        except (tracks.TrackError, OSError) as error:
            QMessageBox.warning(self, "No se pudo guardar el INI", str(error))
            self.statusMessage.emit(f"Circuitos: {error}")

    def _open_track(self) -> None:
        if self._selected is not None:
            self.openRequested.emit(str(self._selected.folder))

    def _open_ini(self) -> None:
        if self._selected is None or self.file_list.currentItem() is None:
            return
        relative = self.file_list.currentItem().data(Qt.ItemDataRole.UserRole)
        if not isinstance(relative, str):
            return
        self.openIniRequested.emit(str(self._selected.folder / relative))
