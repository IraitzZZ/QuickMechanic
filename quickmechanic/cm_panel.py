"""Tarjeta de integracion local con Assetto Corsa Content Manager."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import content_manager, theme


class ContentManagerPanel(QFrame):
    """Muestra si CM está instalado y ofrece abrirlo o resincronizar la biblioteca."""

    syncRequested = pyqtSignal()
    pathChanged = pyqtSignal(str)

    def __init__(self, executable: str | Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("integrationCard")
        self._executable: Path | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)

        mark = QLabel("CM")
        mark.setObjectName("integrationMark")
        mark.setFixedSize(34, 34)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(mark)

        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(2)
        title_row = QHBoxLayout()
        title = QLabel("CONTENT MANAGER")
        title.setObjectName("integrationTitle")
        title_row.addWidget(title)
        self.status = QLabel("")
        self.status.setObjectName("integrationStatus")
        title_row.addWidget(self.status)
        title_row.addStretch(1)
        details.addLayout(title_row)
        self.path_label = QLabel("")
        self.path_label.setObjectName("integrationPath")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.addWidget(self.path_label)
        row.addLayout(details, 1)

        self.choose_button = QPushButton("Elegir .exe")
        self.choose_button.setObjectName("ghost")
        self.choose_button.clicked.connect(self._choose)
        row.addWidget(self.choose_button)
        self.open_button = QPushButton("Abrir CM")
        self.open_button.setObjectName("headerButton")
        self.open_button.clicked.connect(self._open)
        row.addWidget(self.open_button)
        self.sync_button = QPushButton("Sincronizar coches")
        self.sync_button.setObjectName("primary")
        self.sync_button.setToolTip(
            "Vuelve a escanear content/cars tras instalar o extraer coches. "
            "No requiere ni simula una API de Content Manager."
        )
        self.sync_button.clicked.connect(self.syncRequested.emit)
        row.addWidget(self.sync_button)
        self.set_executable(executable)

    @property
    def executable(self) -> Path | None:
        return self._executable

    def set_executable(self, executable: str | Path | None) -> None:
        path = Path(executable).expanduser() if executable else None
        try:
            available = bool(path and path.is_file() and path.suffix.lower() == ".exe")
        except OSError:
            available = False
        self._executable = path if available else None
        if self._executable:
            self.path_label.setText(str(self._executable))
            self.path_label.setToolTip(str(self._executable))
            self.status.setText("●  DETECTADO")
            self.status.setStyleSheet(f"color: {theme.OK}; font-weight: 700;")
        else:
            self.path_label.setText("No encontrado · puedes elegir Content Manager.exe")
            self.path_label.setToolTip("")
            self.status.setText("●  SIN CONFIGURAR")
            self.status.setStyleSheet(f"color: {theme.WARN}; font-weight: 700;")
        self.open_button.setEnabled(self._executable is not None)

    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Assetto Corsa Content Manager", str(self._executable or content_manager.DEFAULT_PATH),
            "Content Manager (*.exe);;Ejecutables (*.exe)",
        )
        if not path:
            return
        selected = Path(path)
        if selected.name.casefold() != "content manager.exe":
            # Algunos usuarios renombran el ejecutable; cualquier .exe elegido se admite.
            if selected.suffix.lower() != ".exe":
                return
        self.set_executable(selected)
        if self._executable is not None:
            self.pathChanged.emit(str(self._executable))

    def _open(self) -> None:
        if self._executable is None:
            return
        try:
            content_manager.launch(self._executable)
        except (OSError, ValueError) as error:
            self.status.setText("●  ERROR AL ABRIR")
            self.status.setStyleSheet(f"color: {theme.DANGER}; font-weight: 700;")
            self.path_label.setToolTip(str(error))
