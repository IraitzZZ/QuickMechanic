"""Integración opcional de inicio de Windows para Quick Mechanic."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "QuickMechanic"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command() -> str:
    """Comando del ejecutable actual o del intérprete/script en desarrollo."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --background'
    if sys.argv and sys.argv[0].startswith("-"):
        return f'"{Path(sys.executable)}" -m quickmechanic --background'
    script = Path(sys.argv[0]).resolve()
    if script.name == "__main__.py" and script.parent.name == "quickmechanic":
        return f'"{Path(sys.executable)}" -m quickmechanic --background'
    return f'"{Path(sys.executable)}" "{script}" --background'


def set_windows_startup(enabled: bool, *, registry=None, command_factory=None) -> tuple[bool, str]:
    """Activa o elimina el valor HKCU Run; no opera al importar y no requiere elevación."""
    if os.name != "nt":
        return False, "El inicio automático solo está disponible en Windows."
    try:
        if registry is None:
            import winreg as registry
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_SET_VALUE) as key:
            if enabled:
                command = (command_factory or startup_command)()
                registry.SetValueEx(key, APP_NAME, 0, registry.REG_SZ, command)
                return True, "Quick Mechanic se iniciará en segundo plano al iniciar Windows."
            try:
                registry.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        return True, "Inicio automático de Quick Mechanic desactivado."
    except OSError as error:
        return False, f"No se pudo cambiar el inicio de Windows: {error}"
