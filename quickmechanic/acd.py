"""Desempaquetado de ``data.acd`` con quickBMS (herramienta incluida).

AC prioriza ``data.acd`` sobre la carpeta ``data/``. Por eso, tras extraerlo,
el original se renombra a ``data.acd.bak`` (nunca se borra) para que el juego
use la carpeta ``data/`` editable y el original siga recuperable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _roots() -> list[Path]:
    roots: list[Path] = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    roots.append(Path(__file__).resolve().parent.parent)
    roots.append(Path.cwd())
    return roots


def find_quickbms() -> Optional[Path]:
    """Ruta a quickbms.exe incluido, o None si no está."""
    for root in _roots():
        candidate = root / "tools" / "quickbms" / "quickbms.exe"
        if candidate.is_file():
            return candidate
    return None


def find_script() -> Optional[Path]:
    """Ruta al script assetto_corsa_acd.bms, o None si no está."""
    for root in _roots():
        candidate = root / "tools" / "assetto_corsa_acd.bms"
        if candidate.is_file():
            return candidate
    return None


def needs_unpack(car_dir: Path) -> bool:
    """True si el coche tiene data.acd y todavía no tiene carpeta data/ utilizable."""
    return (car_dir / "data.acd").is_file() and not (car_dir / "data").is_dir()


def disable_acd(car_dir: Path) -> bool:
    """Renombra data.acd a data.acd.bak. Devuelve True si ya no queda data.acd."""
    acd = car_dir / "data.acd"
    if not acd.exists():
        return True
    bak = car_dir / "data.acd.bak"
    if bak.exists():
        # No pisamos un respaldo anterior: se conserva el original con sufijo nuevo.
        bak = car_dir / f"data.acd.{os.getpid()}.bak"
    try:
        acd.rename(bak)
        return True
    except OSError:
        return False


def unpack(car_dir: Path, disable_original: bool = True) -> tuple[bool, str]:
    """Extrae data.acd en car_dir/data. Devuelve (ok, mensaje)."""
    acd = car_dir / "data.acd"
    if not acd.is_file():
        return False, "El coche no tiene data.acd."
    exe = find_quickbms()
    script = find_script()
    if exe is None or script is None:
        return False, "No se encontró quickBMS o el script assetto_corsa_acd.bms."
    data_dir = car_dir / "data"
    data_dir.mkdir(exist_ok=True)
    try:
        result = subprocess.run(
            [str(exe), "-o", str(script), str(acd), str(data_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(exe.parent),
            creationflags=_CREATE_NO_WINDOW,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"quickBMS falló: {exc}"
    if result.returncode != 0:
        return False, f"quickBMS devolvió {result.returncode}: {result.stderr.strip()[:300]}"
    if not any(data_dir.iterdir()):
        return False, "quickBMS no extrajo ningún fichero."
    if disable_original and not disable_acd(car_dir):
        return False, "Se extrajo data/, pero no se pudo renombrar data.acd."
    return True, "data.acd extraído en data/ (original guardado como data.acd.bak)."
