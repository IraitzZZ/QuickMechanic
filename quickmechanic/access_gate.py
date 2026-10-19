"""Puerta de acceso de Quick Mechanic: inicio de sesión con Discord y revalidación de membresía.

La decisión la toma siempre el servidor (ver discord_link). Esta pantalla solo
muestra el estado real: no hay fases simuladas ni se acepta un indicador local.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from . import APP_NAME, discord_link
from .branding import brand_pixmap
from .discord_link import Access, Status
from .qt_i18n import QDialog, QLabel, QPushButton

REVALIDATE_MS = 10 * 60 * 1000  # revalidación periódica con la app abierta
RETRY_MS = 60 * 1000  # nuevo intento si Discord o el servicio no respondieron

_CHECK_PHASES = (
    "Conectando con Discord",
    "Autorizando en el navegador",
    "Comprobando la membresía del servidor",
    "Preparando el acceso",
)
_BLOCKED_TITLES = {
    Status.NOT_MEMBER: "Acceso denegado",
    Status.SESSION_EXPIRED: "Tu sesión ha caducado",
    Status.UNAVAILABLE: "No podemos comprobar tu acceso",
    Status.FAILED: "No se completó la verificación",
    Status.NOT_SIGNED_IN: "Conecta tu cuenta de Discord",
}


def _invoke(fn: Callable[[], None]) -> None:
    fn()


class _MainThreadCalls(QObject):
    """Lleva al hilo de la interfaz lo que llega desde hilos de fondo."""

    call = pyqtSignal(object)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.call.connect(_invoke)

    def post(self, fn: Callable[[], None]) -> None:
        try:
            self.call.emit(fn)
        except RuntimeError:
            pass  # el destinatario se cerró mientras esperábamos

    def run(self, work: Callable[[], object], done: Callable[[object], None]) -> None:
        def worker() -> None:
            try:
                result = work()
            except Exception:  # noqa: BLE001 - nunca dejar la puerta bloqueada en silencio
                result = Access(Status.UNAVAILABLE, error="unavailable")
            self.post(lambda: done(result))

        threading.Thread(target=worker, daemon=True).start()


class AccessMonitor(QObject):
    """Estado de acceso de la sesión abierta y revalidación periódica contra Discord."""

    changed = pyqtSignal(object)  # Access

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._calls = _MainThreadCalls(self)
        self._token: str | None = None
        self._busy = False
        self.access = Access(Status.NOT_SIGNED_IN)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_now)

    def attach(self, token: str, access: Access) -> None:
        self._token = token
        self._timer.start(REVALIDATE_MS)
        self._publish(access)

    def check_now(self) -> None:
        if self._busy:
            return
        token = self._token
        if token is None:
            self._publish(Access(Status.NOT_SIGNED_IN))
            return
        self._busy = True
        self._calls.run(lambda: discord_link.verify_session(token), self._on_checked)

    def sign_out(self) -> None:
        self._token = None
        self._timer.stop()
        self._calls.run(discord_link.sign_out, lambda _: self._publish(Access(Status.NOT_SIGNED_IN)))

    def _on_checked(self, access: Access) -> None:
        self._busy = False
        if self._token is None:
            return  # la sesión se cerró mientras se comprobaba
        if access.status in (Status.NOT_MEMBER, Status.SESSION_EXPIRED):
            self._token = None
            self._timer.stop()
        elif access.status is Status.UNAVAILABLE:
            self._timer.start(RETRY_MS)  # no sabemos si sigue en el servidor: no se revoca
        else:
            self._timer.start(REVALIDATE_MS)
        self._publish(access)

    def _publish(self, access: Access) -> None:
        self.access = access
        self.changed.emit(access)


def _page() -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(14)
    return page, layout


class AccessGate(QDialog):
    """Pantalla de acceso obligatoria. Solo se acepta con una confirmación del servidor."""

    def __init__(self, monitor: AccessMonitor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Acceso · {APP_NAME}")
        self.setModal(True)
        self.setMinimumSize(600, 560)
        self.setObjectName("guideDialog")
        self._monitor = monitor
        self._calls = _MainThreadCalls(self)
        self._busy = False
        self._granted = False

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        hero = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(brand_pixmap(72))
        hero.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        eyebrow = QLabel("ACCESO · SERVIDOR OFICIAL")
        eyebrow.setObjectName("guideEyebrow")
        title = QLabel("QuickMechanic Access")
        title.setObjectName("guideTitle")
        subtitle = QLabel("Tu taller digital. Tu comunidad. Tu acceso.")
        subtitle.setObjectName("guideSubtitle")
        text.addWidget(eyebrow)
        text.addWidget(title)
        text.addWidget(subtitle)
        hero.addLayout(text, 1)
        root.addLayout(hero)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)
        self._stack.addWidget(self._welcome_page())  # 0
        self._stack.addWidget(self._checking_page())  # 1
        self._stack.addWidget(self._blocked_page())  # 2

        footer = QHBoxLayout()
        secure = QLabel("● Conexión segura con Discord (OAuth2). La app nunca ve tu contraseña.")
        secure.setObjectName("guideProgress")
        secure.setWordWrap(True)
        footer.addWidget(secure, 1)
        quit_button = QPushButton("Salir")
        quit_button.setObjectName("ghost")
        quit_button.clicked.connect(self.reject)
        footer.addWidget(quit_button)
        root.addLayout(footer)

    # --- Páginas --------------------------------------------------------

    def _welcome_page(self) -> QWidget:
        page, layout = _page()
        body = QLabel(
            "Quick Mechanic solo se usa con una cuenta que pertenezca al servidor oficial de Discord. "
            "La membresía se comprueba en el servidor cada vez que la app se abre."
        )
        body.setObjectName("guideBody")
        body.setWordWrap(True)
        layout.addWidget(body)
        steps = QLabel(
            "01  Inicia sesión en Discord\n"
            "02  Comprobamos tu membresía del servidor\n"
            "03  Accedes a Quick Mechanic"
        )
        steps.setObjectName("guideProgress")
        layout.addWidget(steps)
        layout.addStretch(1)
        self._connect_button = QPushButton("Continuar con Discord")
        self._connect_button.setObjectName("heroButton")
        self._connect_button.clicked.connect(self._start_login)
        layout.addWidget(self._connect_button, 0, Qt.AlignmentFlag.AlignLeft)
        return page

    def _checking_page(self) -> QWidget:
        page, layout = _page()
        heading = QLabel("Verificando tu acceso")
        heading.setObjectName("guideStep")
        layout.addWidget(heading)
        self._phase_labels: list[QLabel] = []
        for text in _CHECK_PHASES:
            label = QLabel(text)
            label.setObjectName("guideBody")
            self._phase_labels.append(label)
            layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _blocked_page(self) -> QWidget:
        page, layout = _page()
        self._blocked_title = QLabel()
        self._blocked_title.setObjectName("guideStep")
        self._blocked_title.setWordWrap(True)
        layout.addWidget(self._blocked_title)
        self._blocked_body = QLabel()
        self._blocked_body.setObjectName("guideBody")
        self._blocked_body.setWordWrap(True)
        layout.addWidget(self._blocked_body)
        layout.addStretch(1)
        row = QHBoxLayout()
        self._join_button = QPushButton("Unirse al servidor  ↗")
        self._join_button.setObjectName("heroButton")
        self._join_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(discord_link.INVITE_URL)))
        row.addWidget(self._join_button)
        self._retry_button = QPushButton("Volver a comprobar")
        self._retry_button.setObjectName("primary")
        self._retry_button.clicked.connect(self._retry)
        row.addWidget(self._retry_button)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    # --- Estados --------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._connect_button.setEnabled(not busy)
        self._retry_button.setEnabled(not busy)

    def _show_welcome(self) -> None:
        self._stack.setCurrentIndex(0)
        self._set_busy(False)

    def _show_checking(self, phase: int) -> None:
        for index, label in enumerate(self._phase_labels):
            marker = "✓" if index < phase else "›" if index == phase else "·"
            label.setText(f"{marker}  {_CHECK_PHASES[index]}")
        self._stack.setCurrentIndex(1)
        self._set_busy(True)

    def _show_blocked(self, access: Access) -> None:
        self._blocked_title.setText(_BLOCKED_TITLES.get(access.status, _BLOCKED_TITLES[Status.FAILED]))
        self._blocked_body.setText(discord_link.error_message(access.error))
        self._join_button.setVisible(access.status is Status.NOT_MEMBER)
        self._stack.setCurrentIndex(2)
        self._set_busy(False)

    # --- Acciones -------------------------------------------------------

    def run(self, initial: Access | None = None) -> bool:
        """Muestra la puerta. Devuelve True solo si el servidor confirmó la membresía."""
        self._granted = False
        if initial is not None and initial.status is not Status.NOT_SIGNED_IN:
            self._show_blocked(initial)
        else:
            token = discord_link.stored_token()
            if token is None:
                self._show_welcome()
            else:
                self._check(token)
        self.exec()
        return self._granted

    def _check(self, token: str) -> None:
        self._show_checking(2)
        self._calls.run(
            lambda: discord_link.verify_session(token),
            lambda access: self._on_verified(token, access),
        )

    def _on_verified(self, token: str, access: Access) -> None:
        if access.granted:
            self._accept(token, access)
        else:
            self._show_blocked(access)

    def _start_login(self) -> None:
        self._show_checking(1)
        try:
            discord_link.start_login(
                lambda token, access: self._calls.post(lambda: self._on_login(token, access))
            )
        except OSError:
            self._show_blocked(Access(Status.UNAVAILABLE, error="unavailable"))

    def _on_login(self, token: str | None, access: Access) -> None:
        if token is not None and access.granted:
            self._accept(token, access)
        else:
            self._show_blocked(access)

    def _retry(self) -> None:
        token = discord_link.stored_token()
        if token is None:
            self._start_login()
        else:
            self._check(token)

    def _accept(self, token: str, access: Access) -> None:
        if not self.isVisible():
            return  # el usuario cerró la puerta mientras llegaba la respuesta
        self._granted = True
        self._monitor.attach(token, access)
        self.accept()
