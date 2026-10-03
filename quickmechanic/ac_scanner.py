"""Localiza la instalacion de Assetto Corsa y lista los coches instalados.

Lee el registro de Steam y sus librerias (``steamapps/libraryfolders.vdf``) para
encontrar la carpeta del juego, y despues recorre ``content/cars``.

Un coche puede tener la fisica de dos maneras:

* carpeta ``data/`` con los .ini -> editable directamente.
* ``data.acd`` (archivo propio de AC, comprimido) -> hay que extraerla antes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import ini_editor

try:  # solo existe en Windows; el resto de la app funciona igual sin el
    import winreg  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - en Linux/Mac
    winreg = None  # type: ignore[assignment]

__all__ = ["Car", "find_ac_root", "list_cars", "steam_libraries"]

_STEAM_KEYS = (
    r"SOFTWARE\WOW6432Node\Valve\Steam",
    r"SOFTWARE\Valve\Steam",
)

_MANUAL_CANDIDATES = (
    r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa",
    r"C:\Program Files\Steam\steamapps\common\assettocorsa",
    r"D:\Steam\steamapps\common\assettocorsa",
    r"D:\SteamLibrary\steamapps\common\assettocorsa",
    r"E:\SteamLibrary\steamapps\common\assettocorsa",
    r"F:\SteamLibrary\steamapps\common\assettocorsa",
)


@dataclass
class Car:
    """Un coche dentro de ``content/cars``."""

    folder: Path
    name: str
    ui_name: str
    has_open_data: bool
    has_acd: bool

    @property
    def data_dir(self) -> Path:
        return self.folder / "data"

    @property
    def engine_ini(self) -> Path:
        return self.data_dir / "engine.ini"

    @property
    def ui_json(self) -> Path:
        return self.folder / "ui" / "ui_car.json"

    @property
    def editable(self) -> bool:
        return self.has_open_data

    @property
    def status(self) -> str:
        if self.has_open_data:
            return "editable"
        if self.has_acd:
            return "data.acd"
        return "sin datos"

    @classmethod
    def from_data_dir(cls, data_dir: str | Path) -> Car:
        """Crea un coche a partir de una carpeta ``data`` suelta (extraida a mano)."""
        data_dir = Path(data_dir)
        folder = data_dir.parent
        ui_name = ini_editor.read_ui_car_name(folder / "ui" / "ui_car.json") or folder.name
        return cls(
            folder=folder,
            name=folder.name,
            ui_name=ui_name,
            has_open_data=(data_dir / "engine.ini").is_file(),
            has_acd=(folder / "data.acd").is_file(),
        )


def _steam_install_paths() -> list[Path]:
    roots: list[Path] = []
    if winreg is not None:
        for key_path in _STEAM_KEYS:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        value = winreg.QueryValueEx(key, "InstallPath")[0]
                except OSError:
                    continue
                path = Path(str(value))
                if path.is_dir() and path not in roots:
                    roots.append(path)
    for fallback in (Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")):
        if fallback.is_dir() and fallback not in roots:
            roots.append(fallback)
    return roots


def _library_paths(steam_root: Path) -> list[Path]:
    """Todas las librerias de Steam declaradas en libraryfolders.vdf."""
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        found = re.findall(r'"path"\s+"([^"]+)"', text)
        found += re.findall(r'^\s*"\d+"\s+"([^"]+)"', text, re.MULTILINE)
        for raw in found:
            candidate = Path(raw.replace("\\\\", "\\"))
            if candidate.is_dir() and candidate not in libraries:
                libraries.append(candidate)
    return libraries


def steam_libraries() -> list[Path]:
    libraries: list[Path] = []
    for root in _steam_install_paths():
        for library in _library_paths(root):
            if library not in libraries:
                libraries.append(library)
    return libraries


def find_ac_root(extra: list[str | Path] | tuple[str | Path, ...] = ()) -> Path | None:
    """Devuelve la carpeta raiz de Assetto Corsa, o None si no se encuentra.

    ``extra`` permite probar primero rutas dadas por el usuario.
    """
    candidates: list[Path] = [Path(p) for p in extra]

    for library in steam_libraries():
        candidates.append(library / "steamapps" / "common" / "assettocorsa")
    candidates += [Path(p) for p in _MANUAL_CANDIDATES]

    for candidate in candidates:
        try:
            if (candidate / "content" / "cars").is_dir():
                return candidate
        except OSError:
            continue
    return None


def list_cars(ac_root: str | Path) -> list[Car]:
    """Lista los coches de ``content/cars`` ordenados por nombre visible."""
    cars_dir = Path(ac_root) / "content" / "cars"
    cars: list[Car] = []
    if not cars_dir.is_dir():
        return cars

    for entry in sorted(cars_dir.iterdir(), key=lambda p: p.name.lower()):
        try:
            if not entry.is_dir():
                continue
            ui_name = ini_editor.read_ui_car_name(entry / "ui" / "ui_car.json") or entry.name
            cars.append(
                Car(
                    folder=entry,
                    name=entry.name,
                    ui_name=ui_name,
                    has_open_data=(entry / "data" / "engine.ini").is_file(),
                    has_acd=(entry / "data.acd").is_file(),
                )
            )
        except OSError:
            continue

    cars.sort(key=lambda car: (car.ui_name or car.name).lower())
    return cars
