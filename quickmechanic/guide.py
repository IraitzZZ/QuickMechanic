"""Guia de puesta en marcha y ayuda contextual de Quick Mechanic."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import APP_NAME, theme
from .branding import brand_pixmap

DISCORD_URL = "https://discord.gg/pWE5yEKexW"


class QuickGuideDialog(QDialog):
    """Bienvenida compacta, navegable y también accesible desde el botón Ayuda."""

    PAGES = (
        ("01  ·  TU GARAJE", "Busca un coche por nombre o marca y guárdalo en favoritos. "
         "La previsualización usa la imagen preview de la skin seleccionada; amplíala desde su tarjeta."),
        ("02  ·  AJUSTA CON CRITERIO", "Motor: consulta los valores leídos de power.lut y edita sus puntos en la tabla. "
         "Caja: ajusta marchas y grupo final. Chasis: prueba muelles, amortiguadores, geometría, frenos y presiones con sus unidades reales."),
        ("03  ·  PERFILES Y CAMBIOS", "Guarda una configuración como perfil, compara resultados en el resumen y usa "
         "Ctrl+Z / Ctrl+Y para deshacer o rehacer. Nada se escribe en el juego hasta pulsar Guardar."),
        ("04  ·  PROTEGE EL ORIGINAL", "Antes de guardar crea una copia ZIP y conserva el .bak original y el formato. Los coches con data.acd "
         "requieren extraer data con Content Manager; Quick Mechanic no modifica data.acd."),
        ("05  ·  COMUNIDAD Y CONTENT MANAGER", "Abre Discord para encontrar ayuda y avisos de nuevas versiones. "
         "Content Manager instala o extrae contenido; pulsa Sincronizar coches para refrescar la biblioteca. "
         "Quick Mechanic no descarga ni instala actualizaciones automáticamente."),
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        first_run: bool = False,
        show_on_start: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Guía · {APP_NAME}")
        self.setModal(True)
        self.setMinimumSize(640, 440)
        self.setObjectName("guideDialog")
        self._page = 0
        self._first_run = first_run
        self.show_on_start = bool(show_on_start)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(16)

        hero = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(brand_pixmap(72))
        hero.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        eyebrow = QLabel("QUICK START · EDICIÓN SEGURA")
        eyebrow.setObjectName("guideEyebrow")
        text.addWidget(eyebrow)
        title = QLabel("Bienvenido al box")
        title.setObjectName("guideTitle")
        text.addWidget(title)
        sub = QLabel("Tu centro de ingeniería para Assetto Corsa.")
        sub.setObjectName("guideSubtitle")
        text.addWidget(sub)
        hero.addLayout(text, 1)
        root.addLayout(hero)

        community = QHBoxLayout()
        community_note = QLabel("COMUNIDAD, AYUDA Y AVISOS DE NUEVAS VERSIONES · EL ENLACE ABRE DISCORD")
        community_note.setObjectName("guideEyebrow")
        community.addWidget(community_note, 1)
        self.discord_button = QPushButton("Abrir Discord  ↗")
        self.discord_button.setObjectName("heroButton")
        self.discord_button.setToolTip("Visita la comunidad de SuperIraitz para novedades y ayuda")
        self.discord_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL))
        )
        community.addWidget(self.discord_button)
        root.addLayout(community)

        self.card = QWidget()
        self.card.setObjectName("guideCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)
        self.step = QLabel("")
        self.step.setObjectName("guideStep")
        card_layout.addWidget(self.step)
        self.body = QLabel("")
        self.body.setObjectName("guideBody")
        self.body.setWordWrap(True)
        self.body.setMinimumHeight(78)
        card_layout.addWidget(self.body)
        root.addWidget(self.card, 1)

        footer = QHBoxLayout()
        self.progress = QLabel("")
        self.progress.setObjectName("guideProgress")
        footer.addWidget(self.progress, 0)
        if self._first_run:
            self.show_on_start_check = QCheckBox("Mostrar al iniciar")
            self.show_on_start_check.setObjectName("guideStartup")
            self.show_on_start_check.setChecked(self.show_on_start)
            self.show_on_start_check.toggled.connect(self._set_show_on_start)
            footer.addWidget(self.show_on_start_check, 1)
        else:
            footer.addStretch(1)
        self.back_button = QPushButton("Anterior")
        self.back_button.setObjectName("ghost")
        self.back_button.clicked.connect(self._previous)
        footer.addWidget(self.back_button)
        self.next_button = QPushButton("Siguiente")
        self.next_button.setObjectName("primary")
        self.next_button.clicked.connect(self._next)
        footer.addWidget(self.next_button)
        root.addLayout(footer)
        self._render_page()

    def _render_page(self) -> None:
        title, text = self.PAGES[self._page]
        self.step.setText(title)
        self.body.setText(text)
        self.progress.setText(f"GUÍA  {self._page + 1:02d} / {len(self.PAGES):02d}")
        self.back_button.setEnabled(self._page > 0)
        self.next_button.setText("Empezar a trabajar" if self._page == len(self.PAGES) - 1 else "Siguiente")

    def _set_show_on_start(self, enabled: bool) -> None:
        self.show_on_start = bool(enabled)

    def _previous(self) -> None:
        self._page = max(0, self._page - 1)
        self._render_page()

    def _next(self) -> None:
        if self._page < len(self.PAGES) - 1:
            self._page += 1
            self._render_page()
            return
        self.accept()
