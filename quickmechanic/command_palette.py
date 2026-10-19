"""Paleta de comandos (Ctrl+K): busca páginas y acciones de QuickMechanic por texto."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QListWidgetItem, QVBoxLayout, QWidget

from .qt_i18n import QDialog, QLabel, QLineEdit, QListWidget


@dataclass(frozen=True)
class Command:
    title: str
    group: str
    action: Callable[[], None]
    enabled: bool = True
    keywords: str = ""


def _fold(text: str) -> str:
    """Minúsculas sin tildes, para que «motor» encuentre «Motor» y «diagnóstico» encuentre «diagnostico»."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def filter_commands(commands: list[Command], query: str) -> list[Command]:
    """Devuelve los comandos habilitados cuyo texto contiene todas las palabras de la búsqueda."""
    words = _fold(query).split()
    matches = []
    for command in commands:
        if not command.enabled:
            continue
        haystack = _fold(f"{command.title} {command.group} {command.keywords}")
        if all(word in haystack for word in words):
            matches.append(command)
    return matches


class _ListNavigator(QObject):
    """Permite usar las flechas arriba/abajo desde el buscador sin quitarle el foco."""

    def __init__(self, palette: CommandPalette) -> None:
        super().__init__(palette)
        self._palette = palette

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802 - API de Qt
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._palette.move_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self._palette.move_selection(-1)
                return True
        return False


class CommandPalette(QDialog):
    """Diálogo modal con un buscador y la lista de comandos que coinciden."""

    def __init__(self, commands: list[Command], parent: QWidget | None = None, query: str = "") -> None:
        super().__init__(parent)
        self._commands = list(commands)
        self._visible: list[Command] = []
        self._chosen: Command | None = None
        self.setWindowTitle("Buscar herramienta")
        self.setModal(True)
        self.setMinimumSize(620, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel("Escribe el nombre de una página o acción · ↑ ↓ para elegir · Enter para abrir")
        hint.setObjectName("pageDescription")
        layout.addWidget(hint)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Motor, neumáticos, guardar, exportar...")
        self.search.setObjectName("paletteSearch")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._accept_current)
        self._navigator = _ListNavigator(self)
        self.search.installEventFilter(self._navigator)
        layout.addWidget(self.search)

        self.results = QListWidget()
        self.results.setObjectName("paletteResults")
        self.results.itemActivated.connect(lambda _item: self._accept_current())
        layout.addWidget(self.results, 1)

        self.search.setText(query)
        self._refresh(query)
        self.search.setFocus()

    @property
    def chosen(self) -> Command | None:
        """Comando elegido por el usuario, o None si cerró sin elegir."""
        return self._chosen

    def visible_titles(self) -> list[str]:
        return [command.title for command in self._visible]

    def move_selection(self, step: int) -> None:
        count = self.results.count()
        if count == 0:
            return
        row = max(0, min(count - 1, self.results.currentRow() + step))
        self.results.setCurrentRow(row)

    def _refresh(self, query: str) -> None:
        self._visible = filter_commands(self._commands, query)
        self.results.clear()
        for command in self._visible:
            item = QListWidgetItem(f"{command.title}    ·    {command.group}")
            self.results.addItem(item)
        if self._visible:
            self.results.setCurrentRow(0)

    def _accept_current(self) -> None:
        row = self.results.currentRow()
        if 0 <= row < len(self._visible):
            self._chosen = self._visible[row]
            self.accept()
