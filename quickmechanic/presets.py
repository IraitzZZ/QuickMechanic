"""Perfiles locales de ajustes de coches.

Los perfiles guardan una captura de valores, nunca rutas ni código ejecutable.
Se almacenan fuera de Assetto Corsa y se importan/exportan como JSON.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import settings

__all__ = ["preset_dir", "list_presets", "save_preset", "load_preset", "delete_preset", "export_preset", "import_preset"]

_NAME_RE = re.compile(r"[^\w .()-]+", re.UNICODE)


def _safe_name(name: str) -> str:
    raw = str(name).strip()
    if "/" in raw or chr(92) in raw or raw in {".", ".."}:
        raise ValueError("El nombre no puede contener una ruta")
    cleaned = _NAME_RE.sub("", raw).strip().strip(".")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Escribe un nombre de perfil válido")
    return cleaned[:64]


def preset_dir(car_name: str) -> Path:
    folder = settings.settings_path().parent / "presets" / _safe_name(car_name)
    return folder


def list_presets(car_name: str) -> list[str]:
    try:
        files = preset_dir(car_name).glob("*.json")
        return sorted((path.stem for path in files if path.is_file()), key=str.casefold)
    except OSError:
        return []


def save_preset(car_name: str, name: str, snapshot: dict) -> Path:
    safe = _safe_name(name)
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        raise ValueError("El perfil no tiene un formato compatible")
    folder = preset_dir(car_name)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{safe}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    return target


def load_preset(car_name: str, name: str) -> dict:
    path = preset_dir(car_name) / f"{_safe_name(name)}.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        raise ValueError("El perfil no tiene un formato compatible")
    return snapshot


def delete_preset(car_name: str, name: str) -> bool:
    path = preset_dir(car_name) / f"{_safe_name(name)}.json"
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def export_preset(path: str | Path, snapshot: dict) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".json":
        target = target.with_suffix(".json")
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        raise ValueError("El perfil no tiene un formato compatible")
    target.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def import_preset(path: str | Path) -> dict:
    snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        raise ValueError("El fichero no contiene un perfil Quick Mechanic compatible")
    if not isinstance(snapshot.get("values", {}), dict):
        raise ValueError("El perfil contiene ajustes no válidos")
    return snapshot
