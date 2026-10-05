"""Traduccion de la interfaz: español (idioma base) e ingles.

La app esta escrita en español y ese texto es la clave de traduccion: cada
cadena visible se busca en :mod:`quickmechanic.locales` y, si existe, se
sustituye por su version inglesa. Cuando falta una traduccion se devuelve el
texto original, asi que la interfaz nunca se queda en blanco ni muestra claves
raras: como mucho se ve una frase en español.

Como se traduce:

* :func:`translate` es el motor (texto exacto, plantillas con ``{}`` y
  variantes en MAYUSCULAS usadas por los titulos de las tarjetas).
* :mod:`quickmechanic.qt_i18n` envuelve los widgets de Qt para que cualquier
  texto que se les entregue pase por :func:`translate` sin tocar cada linea.
* :func:`tr` es para el texto que se pinta a mano (splash, informes) o que se
  compone antes de llegar a un widget.

El idioma se guarda en ``settings.json`` (clave ``language``) y se aplica al
arrancar; cambiarlo desde la interfaz reinicia la app para reconstruir las
vistas con el idioma nuevo.
"""
from __future__ import annotations

import re
from typing import Iterable

from . import settings
from .locales import EN_EXACT, EN_TEMPLATES, UI_IGNORED

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "get_language",
    "set_language",
    "load_saved_language",
    "language_label",
    "tr",
    "translate",
    "CORE_TRANSLATED_MODULES",
    "is_translated",
    "scan_missing_translations",
]

DEFAULT_LANGUAGE = "es"
LANGUAGES: dict[str, str] = {"es": "Español", "en": "English"}

#: Modulos cuya superficie visible se mantiene traducida al 100 %. El test de
#: cobertura recorre estos ficheros y falla si aparece un texto sin traducir.
CORE_TRANSLATED_MODULES = (
    "quickmechanic/main.py",
    "quickmechanic/widgets.py",
    "quickmechanic/guide.py",
    "quickmechanic/cm_panel.py",
    "quickmechanic/tabs/dashboard_tab.py",
    "quickmechanic/tabs/engine_tab.py",
    "quickmechanic/tabs/gearbox_tab.py",
    "quickmechanic/tabs/chassis_tab.py",
    "quickmechanic/tabs/info_tab.py",
    "quickmechanic/tabs/aids_tab.py",
    "quickmechanic/tabs/advanced_tab.py",
)

_current = DEFAULT_LANGUAGE

_UPPER: dict[str, str] = {key.upper(): value.upper() for key, value in EN_EXACT.items()}
_UPPER.setdefault("—", "—")


def get_language() -> str:
    """Codigo del idioma activo en esta sesion (``es`` o ``en``)."""
    return _current


def language_label(code: str) -> str:
    return LANGUAGES.get(code, LANGUAGES[DEFAULT_LANGUAGE])


def set_language(code: str, *, persist: bool = False) -> str:
    """Cambia el idioma activo; guarda la preferencia si ``persist``."""
    global _current
    normalized = str(code or "").strip().lower()
    if normalized not in LANGUAGES:
        normalized = DEFAULT_LANGUAGE
    _current = normalized
    if persist:
        try:
            settings.set_value("language", normalized)
        except OSError:
            pass
    return _current


def load_saved_language(default_data: dict | None = None) -> str:
    """Idioma guardado en settings.json (sin escribir nada)."""
    stored = None
    if isinstance(default_data, dict):
        stored = default_data.get("language")
    if stored is None:
        try:
            stored = settings.get("language")
        except OSError:
            stored = None
    return str(stored or DEFAULT_LANGUAGE).strip().lower() if stored else DEFAULT_LANGUAGE


_TEMPLATES: list[tuple[re.Pattern[str], str]] = []


def _template_regex(pattern: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in pattern.split("{}")]
    return re.compile("(.+?)".join(parts), re.DOTALL)


def _templates() -> list[tuple[re.Pattern[str], str]]:
    if not _TEMPLATES:
        _TEMPLATES.extend((_template_regex(source), target) for source, target in EN_TEMPLATES.items())
    return _TEMPLATES


def translate(text: str) -> str:
    """Traduce ``text`` al idioma activo; devuelve el original si no hay tabla."""
    if _current == DEFAULT_LANGUAGE or not isinstance(text, str) or not text:
        return text
    direct = EN_EXACT.get(text)
    if direct is not None:
        return direct
    upper = _UPPER.get(text)
    if upper is not None and text == text.upper():
        return upper
    for regex, target in _templates():
        match = regex.fullmatch(text)
        if match is not None:
            try:
                return target.format(*match.groups())
            except (IndexError, KeyError, ValueError):
                return text
    return text


def tr(text: str, *args, **kwargs) -> str:
    """Traduce y, si llegan argumentos, formatea (``tr("Coche: {}", nombre)``)."""
    translated = translate(text)
    if not args and not kwargs:
        return translated
    try:
        return translated.format(*args, **kwargs)
    except (IndexError, KeyError, ValueError):
        try:
            return text.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            return translated


# ----------------------------------------------------------- cobertura i18n
_PATH_LIKE = re.compile(r"[A-Za-z0-9_./\\-]*[_.\\/][A-Za-z0-9_./\\-]*")
_WORD_LIKE = re.compile(r"[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+")
_STYLE_LIKE = re.compile(
    r"\s*(color|background|border|font|letter-spacing|margin|padding|text-align|"
    r"QLabel|QFrame|QPushButton|QWidget|QGroupBox|QTabWidget|#|\\.)",
    re.I,
)
_MIN_LOWERCASE = re.compile(r"[a-záéíóúñü]{3}")


def _is_text_literal(value: str) -> bool:
    """Descarta codigo, rutas, hojas de estilo y HTML; deja texto visible."""
    if not isinstance(value, str) or len(value) < 3:
        return False
    if any(char in value for char in "\n{}<>"):
        return False
    if value.startswith(("http", "(", "%", "*", "_", "-")):
        return False
    if _STYLE_LIKE.match(value):
        return False
    compact = " " not in value
    if compact and _PATH_LIKE.search(value):
        return False
    if compact and any(char in value for char in "=;\"'"):
        return False
    if bool(_MIN_LOWERCASE.search(value)) or bool(_WORD_LIKE.fullmatch(value)):
        return True
    # Titulos y avisos en mayusculas ("COLECCIÓN DE VEHÍCULOS", "●  SIN CONFIGURAR").
    return bool(re.search(r"[^a-z]{4,}", value)) and " " in value and any(ch.isalpha() for ch in value)


def _docstring_nodes(tree) -> set[int]:
    import ast

    nodes: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            nodes.add(id(body[0].value))
    return nodes


def _fstring_parts(tree) -> set[int]:
    import ast

    parts: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts.update(id(child) for child in ast.walk(node) if isinstance(child, ast.Constant))
    return parts


def is_translated(value: str) -> bool:
    """True si la tabla cubre el texto (aunque la traduccion sea igual al original)."""
    if value in EN_EXACT or value in EN_TEMPLATES:
        return True
    if value == value.upper() and value in _UPPER:
        return True
    return any(regex.fullmatch(value) is not None for regex, _target in _templates())


def scan_missing_translations(modules: Iterable[str] = CORE_TRANSLATED_MODULES) -> list[tuple[str, str]]:
    """[(modulo, texto)] de la superficie visible que aun no tiene traduccion."""
    import ast
    from pathlib import Path

    missing: list[tuple[str, str]] = []
    for module in modules:
        path = Path(module)
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstring_nodes(tree) | _fstring_parts(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in skip or node.value in UI_IGNORED:
                continue
            if not _is_text_literal(node.value):
                continue
            if is_translated(node.value):
                continue
            missing.append((module, node.value))
    return missing


def _main(argv: list[str] | None = None) -> int:
    """``python -m quickmechanic.i18n`` lista los textos sin traducir."""
    import sys

    modules = tuple(argv[1:]) or CORE_TRANSLATED_MODULES
    missing = scan_missing_translations(modules)
    if not missing:
        print("i18n: cobertura completa en los modulos revisados.")
        return 0
    seen: set[str] = set()
    for module, text in missing:
        if text in seen:
            continue
        seen.add(text)
        print(f"{module}\t{text}")
    print(f"i18n: {len(seen)} textos sin traducir.")
    return 1


if __name__ == "__main__":  # pragma: no cover - herramienta de desarrollo
    import sys

    raise SystemExit(_main(sys.argv))
