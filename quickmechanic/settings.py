"""Preferencias de Quick Mechanic (ruta de AC elegida a mano, ultimo coche...).

Se guardan en un JSON fuera del juego, para no ensuciar la instalacion de AC::

    %APPDATA%\\QuickMechanic\\settings.json      (Windows)
    ~/.quickmechanic/settings.json              (Linux/Mac)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["settings_path", "load", "save", "get", "set_value", "delete_value"]

APP_DIR_NAME = "QuickMechanic"


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / APP_DIR_NAME / "settings.json"


def load() -> dict:
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: dict) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> None:
    data = load()
    data[key] = value
    save(data)


def delete_value(key: str) -> None:
    data = load()
    if key in data:
        data.pop(key)
        save(data)
