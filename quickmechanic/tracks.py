"""Descubrimiento de circuitos Assetto Corsa; lectura únicamente, sin instalar ni escribir.

Las carpetas de circuito varían entre mods. Por eso los layouts son candidatos
basados en ``models_<layout>.ini`` y/o carpetas layout con ``data``, ``ai`` o
metadatos UI; la ausencia de un fichero opcional no invalida el circuito.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

__all__ = ["TrackError", "TrackLayout", "TrackInfo", "IniEntry", "scan_tracks", "read_ini", "ini_files", "edit_ini_number"]

_RESERVED_DIRS = {"data", "ai", "ui", "extension", "sfx", "skins", "quickmechanic_backups"}
_MAX_METADATA_BYTES = 512 * 1024
_MAX_INI_BYTES = 4 * 1024 * 1024
_MAX_INI_FILES = 160


class TrackError(ValueError):
    """La biblioteca de circuitos no se puede inspeccionar de forma segura."""


@dataclass(frozen=True)
class IniEntry:
    section: str
    key: str
    value: str


@dataclass(frozen=True)
class TrackLayout:
    name: str
    folder: Path | None
    display_name: str
    ui_file: Path | None
    model_file: Path | None
    data_dir: Path | None
    metadata: dict
    metadata_error: str = ""


@dataclass(frozen=True)
class TrackInfo:
    folder: Path
    name: str
    display_name: str
    country: str
    ui_file: Path | None
    metadata: dict
    metadata_error: str
    layouts: tuple[TrackLayout, ...]
    data_dir: Path | None
    model_files: tuple[Path, ...]


def _safe_path(path: Path, root: Path) -> bool:
    """Comprueba contención y rechaza enlaces simbólicos en toda la ruta."""
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
        current = path.absolute()
        root_absolute = root.absolute()
        while True:
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                return False
            if current == root_absolute:
                break
            if current.parent == current:
                return False
            current = current.parent
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _remove_trailing_commas(text: str) -> str:
    """Admite las comas finales frecuentes en ui_track.json sin dañar strings."""
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
        elif char == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead == len(text) or text[lookahead] not in "]}":
                output.append(char)
        else:
            output.append(char)
        index += 1
    return "".join(output)


def _metadata(path: Path | None, root: Path) -> tuple[dict, str]:
    if path is None or not path.exists():
        return {}, ""
    if not _safe_path(path, root) or not path.is_file():
        return {}, "Ruta UI no segura"
    try:
        if path.stat().st_size > _MAX_METADATA_BYTES:
            return {}, "ui_track.json supera el límite de tamaño"
        text = path.read_text(encoding="utf-8-sig")
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            value = json.loads(_remove_trailing_commas(text))
    except (OSError, UnicodeError, ValueError) as error:
        return {}, f"No se pudo leer ui_track.json: {error}"
    if not isinstance(value, dict):
        return {}, "ui_track.json no contiene un objeto JSON"
    return value, ""


def _direct_data_dir(path: Path, root: Path) -> Path | None:
    candidate = path / "data"
    if candidate.is_dir() and _safe_path(candidate, root):
        return candidate
    return None


def _model_files(folder: Path, root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    try:
        files = folder.glob("models_*.ini")
        for path in files:
            suffix = path.stem[len("models_"):]
            if suffix and path.is_file() and _safe_path(path, root):
                found.setdefault(suffix.casefold(), path)
    except OSError:
        return found
    return found


def _layout_candidates(folder: Path, root: Path, model_files: dict[str, Path]) -> dict[str, Path | None]:
    candidates: dict[str, Path | None] = {}
    try:
        for child in folder.iterdir():
            if child.name.casefold() in _RESERVED_DIRS or not child.is_dir() or not _safe_path(child, root):
                continue
            ui_file = folder / "ui" / child.name / "ui_track.json"
            ai_dir = child / "ai"
            if _direct_data_dir(child, root) or (ai_dir.is_dir() and _safe_path(ai_dir, root)) or (ui_file.is_file() and _safe_path(ui_file, root)):
                candidates.setdefault(child.name.casefold(), child)
    except OSError:
        pass
    for model_name in model_files:
        candidates.setdefault(model_name, None)
    return candidates


def scan_tracks(ac_root: str | Path) -> list[TrackInfo]:
    """Lista circuitos y layouts bajo ``content/tracks`` sin seguir enlaces.

    ``models_<layout>.ini`` y carpetas layout con ``data/``, ``ai/`` o UI propia
    sirven como indicios, no como una validación estricta del formato del juego.
    """
    root = Path(ac_root) / "content" / "tracks"
    current = root
    while True:
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise TrackError("La ruta de circuitos atraviesa un enlace simbólico; se cancela la lectura.")
        if current.parent == current:
            break
        current = current.parent
    if not root.is_dir():
        return []
    try:
        tracks = sorted(
            (path for path in root.iterdir() if path.is_dir() and not path.is_symlink()),
            key=lambda path: path.name.casefold(),
        )
    except OSError as error:
        raise TrackError(f"No se pudo leer la biblioteca de circuitos: {error}") from None

    result: list[TrackInfo] = []
    for folder in tracks:
        if not _safe_path(folder, root):
            continue
        ui_file = folder / "ui" / "ui_track.json"
        metadata, metadata_error = _metadata(ui_file, root)
        model_files = _model_files(folder, root)
        candidates = _layout_candidates(folder, root, model_files)
        layouts: list[TrackLayout] = []
        for folded_name, layout_folder in sorted(candidates.items()):
            name = layout_folder.name if layout_folder is not None else next(
                (model_path.stem[len("models_"):] for model_path in model_files.values()
                 if model_path.stem[len("models_"):].casefold() == folded_name),
                folded_name,
            )
            layout_ui = folder / "ui" / name / "ui_track.json"
            if layout_folder is not None and layout_folder.name.casefold() != name.casefold():
                layout_ui = folder / "ui" / layout_folder.name / "ui_track.json"
            layout_meta, layout_error = _metadata(layout_ui, root)
            layout_data = _direct_data_dir(layout_folder, root) if layout_folder is not None else None
            layout_model = model_files.get(folded_name)
            layouts.append(TrackLayout(
                name=name,
                folder=layout_folder,
                display_name=str(layout_meta.get("name") or name),
                ui_file=layout_ui if layout_meta or layout_error else None,
                model_file=layout_model,
                data_dir=layout_data,
                metadata=layout_meta,
                metadata_error=layout_error,
            ))
        result.append(TrackInfo(
            folder=folder,
            name=folder.name,
            display_name=str(metadata.get("name") or folder.name),
            country=str(metadata.get("country") or ""),
            ui_file=ui_file if metadata or metadata_error else None,
            metadata=metadata,
            metadata_error=metadata_error,
            layouts=tuple(layouts),
            data_dir=_direct_data_dir(folder, root),
            model_files=tuple(sorted(model_files.values(), key=lambda path: path.name.casefold())),
        ))
    return result


def ini_files(track: TrackInfo) -> tuple[Path, ...]:
    """INIs técnicos del circuito/layout, acotados a las ubicaciones conocidas."""
    root = track.folder
    if root.is_symlink() or not root.is_dir():
        return ()
    candidates: list[Path] = list(track.model_files)
    if track.data_dir is not None:
        candidates.extend(track.data_dir.glob("*.ini"))
    for layout in track.layouts:
        if layout.data_dir is not None:
            candidates.extend(layout.data_dir.glob("*.ini"))
    safe = {
        path.resolve(): path
        for path in candidates
        if path.suffix.casefold() == ".ini" and path.is_file() and _safe_path(path, root)
    }
    return tuple(sorted(safe.values(), key=lambda path: path.relative_to(root).as_posix().casefold())[:_MAX_INI_FILES])


def edit_ini_number(
    track: TrackInfo,
    path: str | Path,
    section: str,
    key: str,
    value: float,
    expected_sha256: str,
) -> Path:
    """Edita una clave numérica existente de un INI reconocido, preservando un .bak.

    Rechaza rutas fuera de las ubicaciones inspeccionadas, claves nuevas, valores
    inválidos y archivos modificados desde que la vista los leyó.
    """
    file_path = Path(path)
    try:
        resolved_path = file_path.resolve(strict=True)
        allowed = {candidate.resolve(strict=True) for candidate in ini_files(track)}
        if resolved_path not in allowed or not _safe_path(file_path, track.folder):
            raise TrackError("El INI ya no pertenece a las ubicaciones seguras de este circuito.")
        original = file_path.read_bytes()
    except (OSError, RuntimeError, ValueError):
        raise TrackError("No se pudo volver a validar el INI del circuito.") from None
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise TrackError("El INI cambió desde que se abrió; vuelve a seleccionarlo para evitar sobrescribir cambios.")
    try:
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise TrackError("El valor debe ser un número finito.") from None

    from .ini_editor import ACIni

    editor = ACIni(file_path)
    if not editor.has(section, key):
        raise TrackError("No se crean claves nuevas en archivos de circuito.")
    try:
        old_value = float(editor.get(section, key))
    except (TypeError, ValueError):
        raise TrackError("Esta herramienta solo edita valores numéricos existentes.") from None
    if not math.isfinite(old_value):
        raise TrackError("El valor actual del INI no es un número finito.")
    if numeric_value == old_value:
        return file_path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = file_path.with_name(f"{file_path.name}.qm-{stamp}.bak")
    try:
        with backup_path.open("xb") as backup_file:
            backup_file.write(original)
    except OSError as error:
        raise TrackError(f"No se pudo crear el respaldo del INI: {error}") from None
    editor.set_value(section, key, numeric_value)
    try:
        saved = editor.save(backup=False)
    except OSError as error:
        raise TrackError(f"No se pudo guardar el INI; el respaldo está en {backup_path.name}: {error}") from None
    return saved or file_path


def read_ini(path: str | Path, track_root: str | Path) -> list[IniEntry]:
    """Lee pares de un INI de circuito, sin modificarlo ni seguir enlaces."""
    file_path = Path(path)
    root = Path(track_root)
    if file_path.suffix.casefold() != ".ini" or not _safe_path(file_path, root) or not file_path.is_file():
        raise TrackError("El archivo INI no está dentro de la carpeta del circuito o no es seguro.")
    try:
        if file_path.stat().st_size > _MAX_INI_BYTES:
            raise TrackError("El INI supera el límite de tamaño para inspección.")
        lines = file_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as error:
        raise TrackError(f"No se pudo leer {file_path.name}: {error}") from None
    entries: list[IniEntry] = []
    section = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#", "//")):
            continue
        if stripped.startswith("[") and "]" in stripped:
            section = stripped[1:stripped.index("]")].strip()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = re.split(r"\s[;#]", value, maxsplit=1)[0].strip()
        entries.append(IniEntry(section, key, value))
    return entries
