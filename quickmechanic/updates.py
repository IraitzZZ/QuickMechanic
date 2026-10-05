"""Aviso y descarga de versiones nuevas desde GitHub Releases.

Quick Mechanic consulta la ultima release publicada de su repositorio y avisa
cuando hay algo mas nuevo que la version instalada. Si el usuario acepta, la app
descarga el instalador a ``%APPDATA%\\QuickMechanic\\updates`` y lo abre solo
cuando el usuario pulsa el boton: nunca se ejecuta nada de forma silenciosa.

Todo es tolerante a fallos: sin internet, con 404 (repositorio privado o sin
releases) o con un JSON raro la comprobacion devuelve ``None`` y la app sigue
funcionando sin mensajes de error. El aviso de nueva version es persistente y
se puede cerrar; si la descarga falla, el aviso se queda con el error y un boton
para reintentar.

Las funciones de red aceptan un ``fetch`` inyectable para poder probarlas sin
salir a internet.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from PyQt6.QtCore import QObject, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout

from . import settings
from .i18n import tr
from .qt_i18n import QFrame, QLabel, QMessageBox, QPushButton

__all__ = [
    "GITHUB_REPO",
    "RELEASES_API",
    "RELEASES_PAGE",
    "UpdateAsset",
    "UpdateError",
    "UpdateInfo",
    "UpdateNotice",
    "UpdateWorker",
    "asset_candidates",
    "check_for_update",
    "download_asset",
    "download_installer",
    "extract_setup",
    "is_newer",
    "latest_dir",
    "parse_version",
]

GITHUB_REPO = "IraitzZZ/QuickMechanic"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
USER_AGENT = "QuickMechanic-Updater"
ALLOWED_SUFFIXES = (".exe", ".zip")
INSTALLER_SUFFIXES = (".exe", ".msi")
#: Un ZIP de release solo puede aportar instalador y documentacion.
ARCHIVE_SUFFIXES = (".exe", ".msi", ".txt", ".md", ".json", ".ini", ".ico", ".dll")
MAX_DOWNLOAD_BYTES = 400 * 1024 * 1024
MAX_ARCHIVE_BYTES = 600 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 64


class UpdateError(RuntimeError):
    """Fallo controlado durante la comprobacion o la descarga."""


@dataclass(frozen=True)
class UpdateAsset:
    name: str
    url: str
    size: int = 0


@dataclass(frozen=True)
class UpdateInfo:
    tag: str
    version: tuple[int, ...]
    name: str
    notes: str
    page_url: str
    assets: tuple[UpdateAsset, ...] = ()


# --------------------------------------------------------------------- red
def _default_fetch(url: str, *, timeout: float = 6.0) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL fija)
        return response.read(MAX_DOWNLOAD_BYTES + 1)


def parse_version(text: str) -> tuple[int, ...]:
    """``"v0.2.1"`` -> ``(0, 2, 1)``; devuelve ``()`` si no hay numeros."""
    if not isinstance(text, str):
        return ()
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return ()
    return tuple(int(number) for number in numbers[:6])


def is_newer(candidate: Iterable[int], current: Iterable[int]) -> bool:
    """Compara versiones por partes, rellenando con ceros (0.3 == 0.3.0)."""
    left = list(candidate)
    right = list(current)
    length = max(len(left), len(right))
    left += [0] * (length - len(left))
    right += [0] * (length - len(right))
    return tuple(left) > tuple(right)


def _asset_from_payload(raw) -> UpdateAsset | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    url = str(raw.get("browser_download_url") or "").strip()
    if not name or not name.lower().endswith(ALLOWED_SUFFIXES):
        return None
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    if not url.lower().startswith(("http://", "https://")):
        return None
    size = raw.get("size")
    return UpdateAsset(name=name, url=url, size=int(size) if isinstance(size, (int, float)) else 0)


def _payload_to_info(payload, current_version: str) -> UpdateInfo | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("draft") or payload.get("prerelease"):
        return None
    tag = str(payload.get("tag_name") or payload.get("name") or "").strip()
    version = parse_version(tag)
    if not tag or not version or not is_newer(version, parse_version(current_version)):
        return None
    assets: list[UpdateAsset] = []
    for raw in payload.get("assets") or ():
        asset = _asset_from_payload(raw)
        if asset is not None:
            assets.append(asset)
    page_url = str(payload.get("html_url") or RELEASES_PAGE).strip() or RELEASES_PAGE
    return UpdateInfo(
        tag=tag,
        version=version,
        name=str(payload.get("name") or tag).strip(),
        notes=str(payload.get("body") or "").strip(),
        page_url=page_url,
        assets=tuple(assets),
    )


def check_for_update(
    current_version: str,
    *,
    fetch: Callable[..., bytes] | None = None,
    url: str = RELEASES_API,
    timeout: float = 6.0,
    on_error: Callable[[str], None] | None = None,
) -> UpdateInfo | None:
    """Devuelve la version nueva o ``None`` (sin internet, 404, ya al dia...).

    Nunca lanza ni muestra nada: los fallos se comunican por ``on_error`` y, si
    no hay interesado, se ignoran en silencio (asi el arranque no molesta).
    """
    getter = fetch or _default_fetch
    try:
        raw = getter(url, timeout=timeout)
    except Exception as error:  # red, 404, proxy o SSL: la app sigue igual
        if on_error is not None:
            on_error(_error_text(error))
        return None
    try:
        payload = json.loads(raw if isinstance(raw, (bytes, bytearray, str)) else json.dumps(raw))
    except (TypeError, ValueError) as error:
        if on_error is not None:
            on_error(_error_text(error))
        return None
    return _payload_to_info(payload, current_version)


def _error_text(error: BaseException) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, urllib.error.URLError):
        return str(error.reason or error)
    return str(error) or error.__class__.__name__


def asset_candidates(info: UpdateInfo) -> list[UpdateAsset]:
    """Instaladores primero (``Setup.exe``), luego otros .exe y despues .zip."""
    def rank(asset: UpdateAsset) -> tuple[int, int, str]:
        name = asset.name.lower()
        if name == "setup.exe":
            return (0, 0, name)
        if name.endswith(".exe"):
            return (1, 0, name)
        return (2, 0, name)

    return sorted(info.assets, key=rank)


def latest_dir() -> Path:
    """Carpeta de descargas de la app (fuera del juego y de la carpeta instalada)."""
    return settings.settings_path().parent / "updates"


def download_asset(
    asset: UpdateAsset,
    dest_dir: Path | str | None = None,
    *,
    fetch: Callable[..., bytes] | None = None,
    timeout: float = 60.0,
) -> Path:
    """Descarga el instalador a ``dest_dir``; nunca lo ejecuta."""
    if not asset.name.lower().endswith(ALLOWED_SUFFIXES):
        raise UpdateError(tr("Tipo de archivo no permitido: {0}", asset.name))
    folder = Path(dest_dir) if dest_dir else latest_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise UpdateError(tr("No se pudo crear la carpeta de descargas: {0}", error)) from None
    target = folder / Path(asset.name).name
    getter = fetch or _default_fetch
    try:
        data = getter(asset.url, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as error:
        raise UpdateError(tr("No se pudo descargar: {0}", error)) from None
    except Exception as error:  # red exotica (ssl, proxy...)
        raise UpdateError(tr("No se pudo descargar: {0}", error)) from None
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise UpdateError(tr("La descarga llegó vacía."))
    if asset.size and len(data) != asset.size:
        raise UpdateError(
            tr("Descarga incompleta ({0} de {1} bytes).", len(data), asset.size)
        )
    part = target.with_name(target.name + ".part")
    try:
        part.write_bytes(bytes(data))
        os.replace(part, target)
    except OSError as error:
        part.unlink(missing_ok=True)
        raise UpdateError(tr("No se pudo guardar el archivo: {0}", error)) from None
    return target


def _safe_member(name: str) -> bool:
    """Ruta de ZIP admisible: sin traversal, sin absolutas y con extension conocida."""
    if not name or name.endswith(("/", "\\")):
        return False
    if name.startswith(("/", "\\")) or ":" in name or ".." in name.split("/"):
        return False
    lowered = name.lower()
    return lowered.endswith(ARCHIVE_SUFFIXES)


def extract_setup(archive: Path | str, dest_dir: Path | str | None = None) -> Path:
    """Extrae el instalador de un ZIP de release y devuelve el .exe/.msi listo.

    Los ZIP se tratan como contenido no confiable: se rechaza cualquier entrada
    con traversal, ruta absoluta, enlace o extension no conocida, y solo se
    extraen ficheros dentro de la carpeta de descargas de Quick Mechanic. Si el
    ZIP no trae instalador, se devuelve el propio ZIP.
    """
    path = Path(archive)
    folder = Path(dest_dir) if dest_dir else path.parent
    try:
        with zipfile.ZipFile(path) as bundle:
            members = [info for info in bundle.infolist() if not info.is_dir()]
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise UpdateError(tr("El ZIP trae demasiados archivos."))
            total = sum(info.file_size for info in members)
            if total > MAX_ARCHIVE_BYTES:
                raise UpdateError(tr("El ZIP es demasiado grande para extraerlo."))
            selected = [info for info in members if _safe_member(info.filename)]
            if not selected:
                return path
            folder.mkdir(parents=True, exist_ok=True)
            best: Path | None = None
            for info in selected:
                target = folder / Path(info.filename).name
                with bundle.open(info) as source, target.open("wb") as destino:
                    shutil_copy(source, destino)
                if target.suffix.lower() in INSTALLER_SUFFIXES:
                    if best is None or target.name.lower() == "setup.exe":
                        best = target
    except (zipfile.BadZipFile, OSError) as error:
        raise UpdateError(tr("No se pudo abrir el ZIP: {0}", error)) from None
    return best or path


def shutil_copy(source, destino) -> None:  # pragma: no cover - utilidad simple
    """Copia por bloques sin cargar el archivo entero en memoria."""
    while chunk := source.read(1024 * 1024):
        destino.write(chunk)


def download_installer(
    asset: UpdateAsset,
    dest_dir: Path | str | None = None,
    *,
    fetch: Callable[..., bytes] | None = None,
    timeout: float = 60.0,
) -> Path:
    """Descarga el asset y, si es un ZIP, deja dentro el instalador listo."""
    path = download_asset(asset, dest_dir, fetch=fetch, timeout=timeout)
    if path.suffix.lower() == ".zip":
        return extract_setup(path, path.parent)
    return path


# ------------------------------------------------------------------- hilo
class UpdateWorker(QObject):
    """Comprueba la ultima release fuera del hilo de la interfaz."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, current_version: str, *, fetch=None, timeout: float = 6.0) -> None:
        super().__init__()
        self.current_version = current_version
        self._fetch = fetch
        self._timeout = timeout

    @pyqtSlot()
    def run(self) -> None:
        problem = False

        def on_error(message: str) -> None:
            nonlocal problem
            problem = True
            self.failed.emit(message)

        try:
            info = check_for_update(
                self.current_version,
                fetch=self._fetch,
                timeout=self._timeout,
                on_error=on_error,
            )
        except Exception as error:  # nunca debe tumbar la app
            self.failed.emit(str(error))
            return
        if problem:
            return
        self.finished.emit(info)


class DownloadWorker(QObject):
    """Descarga el instalador en segundo plano."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, asset: UpdateAsset, *, fetch=None, timeout: float = 60.0) -> None:
        super().__init__()
        self.asset = asset
        self._fetch = fetch
        self._timeout = timeout

    @pyqtSlot()
    def run(self) -> None:
        try:
            path = download_installer(self.asset, fetch=self._fetch, timeout=self._timeout)
        except UpdateError as error:
            self.failed.emit(str(error))
            return
        except Exception as error:  # pragma: no cover - red exotica
            self.failed.emit(str(error))
            return
        self.finished.emit(path)


def start_worker(worker: QObject, parent: QObject | None = None) -> QThread:
    """Lanza un worker en su propio hilo y limpia el worker al terminar.

    El ``QThread`` no se destruye solo: quien lo lanza guarda la referencia para
    saber si sigue trabajando, y el dueño del objeto es quien decide cuando
    soltarlo (asi nunca se toca un objeto C++ ya eliminado).
    """
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    for signal in (worker.finished, worker.failed):
        signal.connect(thread.quit)
        signal.connect(worker.deleteLater)
    thread.start()
    return thread


# ------------------------------------------------------------------ aviso
class UpdateNotice(QFrame):
    """Aviso persistente de version nueva (se cierra a mano, nunca solo)."""

    downloadRequested = pyqtSignal()
    openPageRequested = pyqtSignal()
    openDownloadRequested = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("updateNotification")
        self._info: UpdateInfo | None = None
        self._downloaded: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)
        badge = QLabel(tr("ACTUALIZACIÓN"))
        badge.setObjectName("updateBadge")
        top.addWidget(badge)
        self.message = QLabel("")
        self.message.setObjectName("updateMessage")
        self.message.setWordWrap(True)
        top.addWidget(self.message, 1)
        self.download_button = QPushButton(tr("Descargar e instalar"))
        self.download_button.setObjectName("heroButton")
        self.download_button.clicked.connect(self.downloadRequested.emit)
        top.addWidget(self.download_button)
        self.page_button = QPushButton(tr("Ver en GitHub"))
        self.page_button.setObjectName("ghost")
        self.page_button.clicked.connect(self.openPageRequested.emit)
        top.addWidget(self.page_button)
        self.dismiss_button = QPushButton("×")
        self.dismiss_button.setObjectName("iconButton")
        self.dismiss_button.setFixedWidth(34)
        self.dismiss_button.setToolTip(tr("Cerrar el aviso de actualización"))
        self.dismiss_button.clicked.connect(self._dismiss)
        top.addWidget(self.dismiss_button)
        layout.addLayout(top)

        self.detail = QLabel("")
        self.detail.setObjectName("updateDetail")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.hide()

    @property
    def info(self) -> UpdateInfo | None:
        return self._info

    @property
    def downloaded_path(self) -> Path | None:
        return self._downloaded

    def show_available(self, info: UpdateInfo) -> None:
        self._info = info
        self._downloaded = None
        assets = asset_candidates(info)
        self.download_button.setText(tr("Descargar e instalar"))
        self.download_button.setEnabled(bool(assets))
        self.download_button.setVisible(True)
        self.download_button.setToolTip(
            tr("Descarga {0} a tu carpeta de descargas; no lo ejecuta solo", assets[0].name)
            if assets else tr("Esta release no trae instalador (.exe) ni ZIP")
        )
        self.message.setText(tr("Hay una versión nueva disponible: {0}", info.name or info.tag))
        notes = info.notes.splitlines()
        preview = " ".join(line.strip() for line in notes if line.strip())[:220]
        self.detail.setText(
            tr("Versión instalada frente a {0}. {1}", info.tag, preview) if preview
            else tr("Versión nueva {0}. El aviso se queda aquí hasta que lo cierres.", info.tag)
        )
        self.show()

    def show_downloading(self) -> None:
        self.download_button.setEnabled(False)
        self.download_button.setText(tr("Descargando…"))
        self.detail.setText(tr("Descargando el instalador en segundo plano…"))
        self.show()

    def show_downloaded(self, path: Path) -> None:
        self._downloaded = path
        installable = path.suffix.lower() in INSTALLER_SUFFIXES
        self.download_button.setEnabled(True)
        self.download_button.setText(
            tr("Abrir instalador") if installable else tr("Abrir carpeta de descargas")
        )
        self.download_button.setToolTip(
            tr("Abre {0} solo cuando pulses aquí", path.name)
            if installable else tr("Abre la carpeta donde quedó {0}", path.name)
        )
        self.detail.setText(
            tr("Descargado en {0}. Ciérralo desde este aviso cuando lo hayas usado.", str(path))
        )
        self.show()

    def show_error(self, message: str) -> None:
        self.download_button.setEnabled(True)
        self.download_button.setText(tr("Reintentar descarga"))
        self.detail.setText(tr("No se pudo descargar: {0}", message))
        self.show()

    def open_download_folder(self) -> None:
        folder = self._downloaded.parent if self._downloaded else latest_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def launch_downloaded(self) -> None:
        """Abre el instalador descargado (solo tras pulsarlo el usuario)."""
        if self._downloaded is None or not self._downloaded.is_file():
            QMessageBox.information(
                self, tr("Descarga no disponible"), tr("Vuelve a descargar el instalador.")
            )
            return
        if self._downloaded.suffix.lower() in INSTALLER_SUFFIXES:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._downloaded)))
            return
        self.open_download_folder()

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()
