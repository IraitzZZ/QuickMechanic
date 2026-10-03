"""Deteccion y apertura local de Assetto Corsa Content Manager.

Content Manager no ofrece una API local estable para editar setups. Esta capa
solo detecta/abre su ejecutable; la sincronizacion de Quick Mechanic vuelve a
escanear la biblioteca de coches despues de instalar o extraer contenido.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_PATH = Path(r"C:\latest\Content Manager.exe")


def _registry_paths() -> list[Path]:
    """Busca Content Manager en App Paths de Windows, si el registro esta disponible."""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - non-Windows
        return []

    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Content Manager.exe"
    found: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                executable = winreg.QueryValueEx(key, "")[0]
            if executable:
                found.append(Path(str(executable)))
        except OSError:
            continue
    return found


def candidates(configured: str | Path | None = None) -> list[Path]:
    """Rutas probables ordenadas: preferencia guardada, registro y ubicaciones comunes."""
    paths: list[Path] = []
    if configured:
        paths.append(Path(configured).expanduser())
    paths.extend(_registry_paths())
    paths.extend((
        DEFAULT_PATH,
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        / "Programs" / "Content Manager" / "Content Manager.exe",
        Path.home() / "Desktop" / "Content Manager.exe",
        Path(r"C:\Program Files\Content Manager\Content Manager.exe"),
        Path(r"C:\Program Files (x86)\Content Manager\Content Manager.exe"),
    ))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_executable(configured: str | Path | None = None) -> Path | None:
    """Devuelve la primera ruta existente que parece un ejecutable de CM."""
    for path in candidates(configured):
        try:
            if path.is_file() and path.suffix.lower() == ".exe":
                return path
        except OSError:
            continue
    return None


def launch(executable: str | Path) -> subprocess.Popen:
    """Abre Content Manager como proceso independiente."""
    path = Path(executable)
    if path.suffix.lower() != ".exe" or not path.is_file():
        raise FileNotFoundError(f"No se encuentra Content Manager: {path}")
    kwargs = {"cwd": str(path.parent)}
    if os.name == "nt":  # no mostrar una consola adicional en Windows
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
    return subprocess.Popen([str(path)], **kwargs)
