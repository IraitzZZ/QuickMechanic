"""Almacen del taller: setups, versiones, historial, respaldos y clonado.

Todo se guarda **fuera** de Assetto Corsa (en la carpeta de Quick Mechanic), salvo
los respaldos ZIP, que viven junto al coche en ``quickmechanic_backups/`` porque
es donde los espera tambien el modulo de swaps.

Reglas de seguridad que se repiten en todo el modulo:

* nunca se escribe dentro de la carpeta de otro coche al clonar;
* los ficheros ``.qmsetup`` se validan antes de tocarse y nunca traen rutas;
* restaurar un fichero suelto de un respaldo escribe **solo** dentro de la
  carpeta ``data/`` del coche y rechaza traversal, absolutas y enlaces.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import settings
from .integrity import sign_payload, verify_payload

__all__ = [
    "Change",
    "CloneResult",
    "SetupInfo",
    "VersionInfo",
    "BackupInfo",
    "GarageError",
    "changes_between",
    "clone_car",
    "delete_setup",
    "delete_version",
    "export_setup",
    "history_path",
    "import_setup",
    "list_backups",
    "list_setups",
    "list_versions",
    "load_setup",
    "load_version",
    "prune_backups",
    "read_history",
    "record_changes",
    "restore_member",
    "save_setup",
    "save_version",
    "backup_members",
    "suggest_clone_name",
    "setup_circuits",
]

SETUP_KIND = "quickmechanic.setup"
VERSION = 1
_NAME_RE = re.compile(r"[^\w .()+-]+", re.UNICODE)
MAX_HISTORY = 400


class GarageError(Exception):
    """Error de uso (nombre raro, fichero incompatible, ruta insegura)."""


# ------------------------------------------------------------------- utilidades
def root_dir() -> Path:
    return settings.settings_path().parent


def _safe_name(name: str) -> str:
    raw = str(name).strip()
    if "/" in raw or "\\" in raw or raw in {".", ".."}:
        raise GarageError("El nombre no puede contener una ruta")
    cleaned = _NAME_RE.sub("", raw).strip().strip(".")
    if not cleaned or cleaned in {".", ".."}:
        raise GarageError("Escribe un nombre valido")
    return cleaned[:64]


def _car_dir(kind: str, car_name: str) -> Path:
    return root_dir() / kind / _safe_name(car_name)


def _write_json(target: Path, data: dict) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)
    return target


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GarageError(f"No se pudo leer {Path(path).name}: {error}") from None
    if not isinstance(data, dict):
        raise GarageError("El fichero no contiene un objeto valido")
    return data


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _validate_snapshot(snapshot: dict, *, origin: str) -> dict:
    if not isinstance(snapshot, dict) or snapshot.get("version") != VERSION:
        raise GarageError(f"{origin} no tiene un formato compatible (version 1)")
    if not isinstance(snapshot.get("values", {}), dict):
        raise GarageError(f"{origin} no contiene valores validos")
    return snapshot


# -------------------------------------------------- historial de cambios (undo)
@dataclass(frozen=True)
class Change:
    """Un parametro que ha cambiado, con su valor anterior y el nuevo."""

    moment: str
    area: str
    parameter: str
    before: str
    after: str

    @property
    def label(self) -> str:
        return f"{self.area} · {self.parameter}"


def changes_between(before: dict, after: dict) -> list[Change]:
    """Diferencias entre dos capturas de setup, parametro a parametro."""
    moment = _stamp()
    out: list[Change] = []

    def walk(path: str, left, right) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                walk(f"{path}/{key}" if path else str(key), left.get(key), right.get(key))
            return
        if left == right:
            return
        out.append(
            Change(
                moment=moment,
                area=path.split("/")[0] if path else "",
                parameter=path,
                before=_text(left),
                after=_text(right),
            )
        )

    for block in ("values", "advanced"):
        walk(block, before.get(block, {}), after.get(block, {}))
    curve_before = before.get("power_curve") or []
    curve_after = after.get("power_curve") or []
    if curve_before != curve_after:
        cambiados = [
            index for index, (left, right) in enumerate(zip(curve_before, curve_after))
            if left != right
        ]
        antes_curva, despues_curva = _curve_change_text(curve_before, curve_after, cambiados)
        out.append(
            Change(
                moment=moment,
                area="Motor",
                parameter="power_curve",
                before=antes_curva,
                after=despues_curva,
            )
        )
    if (before.get("turbos") or []) != (after.get("turbos") or []):
        out.append(
            Change(
                moment=moment,
                area="Motor",
                parameter="turbos",
                before=f"{len(before.get('turbos') or [])} turbo(s)",
                after=f"{len(after.get('turbos') or [])} turbo(s)",
            )
        )
    return out


def _curve_change_text(before, after, changed: list[int]) -> tuple[str, str]:
    """Resumen legible de los puntos de power.lut que han cambiado."""
    if not changed:
        return f"{len(before)} puntos", f"{len(after)} puntos"
    def resume(rows) -> str:
        trozos = []
        for index in changed[:4]:
            if index >= len(rows):
                continue
            row = rows[index]
            rpm = row[0] if row else 0
            torque = row[-1] if row else 0
            trozos.append(f"punto {index + 1} ({rpm:g} rpm) {torque:g} Nm")
        resto = len(changed) - len(trozos)
        texto = ", ".join(trozos)
        return texto + (f" y {resto} mas" if resto > 0 else "")

    return resume(before), resume(after)


def _text(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def history_path(car_name: str) -> Path:
    return _car_dir("history", car_name) / "changes.json"


def record_changes(car_name: str, changes, *, limit: int = MAX_HISTORY) -> int:
    """Anade cambios al historial del coche y devuelve cuantos se guardaron."""
    entries = [
        {
            "moment": change.moment,
            "area": change.area,
            "parameter": change.parameter,
            "before": change.before,
            "after": change.after,
        }
        for change in changes
    ]
    if not entries:
        return 0
    path = history_path(car_name)
    stored = []
    if path.is_file():
        try:
            stored = _read_json(path).get("changes", [])
        except GarageError:
            stored = []
    stored.extend(entries)
    _write_json(path, {"version": VERSION, "changes": stored[-limit:]})
    return len(entries)


def read_history(car_name: str, limit: int = 200) -> list[Change]:
    """Ultimos cambios registrados del coche, del mas nuevo al mas viejo."""
    path = history_path(car_name)
    if not path.is_file():
        return []
    try:
        stored = _read_json(path).get("changes", [])
    except GarageError:
        return []
    out = []
    for entry in stored[-limit:]:
        if not isinstance(entry, dict):
            continue
        out.append(
            Change(
                moment=str(entry.get("moment", "")),
                area=str(entry.get("area", "")),
                parameter=str(entry.get("parameter", "")),
                before=str(entry.get("before", "")),
                after=str(entry.get("after", "")),
            )
        )
    return list(reversed(out))


# --------------------------------------------------------- gestor de setups
@dataclass(frozen=True)
class SetupInfo:
    """Setup guardado, con el circuito y las condiciones para los que se penso."""

    name: str
    circuit: str
    conditions: str
    style: str
    created: str
    note: str = ""
    path: str = ""

    @property
    def subtitle(self) -> str:
        parts = [part for part in (self.circuit, self.conditions, self.style) if part]
        return " · ".join(parts) or "sin condiciones"


def save_setup(
    car_name: str,
    name: str,
    snapshot: dict,
    *,
    circuit: str = "",
    conditions: str = "",
    style: str = "",
    note: str = "",
) -> Path:
    """Guarda una captura completa como setup con su circuito y condiciones."""
    safe = _safe_name(name)
    _validate_snapshot(snapshot, origin="El setup")
    payload = {
        "kind": SETUP_KIND,
        "version": VERSION,
        "car": car_name,
        "name": safe,
        "circuit": str(circuit).strip()[:48],
        "conditions": str(conditions).strip()[:48],
        "style": str(style).strip()[:24],
        "note": str(note).strip()[:200],
        "created": _stamp(),
        "setup": snapshot,
    }
    return _write_json(_car_dir("setups", car_name) / f"{safe}.qmsetup", payload)


def list_setups(car_name: str) -> list[SetupInfo]:
    folder = _car_dir("setups", car_name)
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob("*.qmsetup"), key=lambda item: item.name.casefold()):
        try:
            data = _read_json(path)
        except GarageError:
            continue
        out.append(
            SetupInfo(
                name=str(data.get("name") or path.stem),
                circuit=str(data.get("circuit", "")),
                conditions=str(data.get("conditions", "")),
                style=str(data.get("style", "")),
                created=str(data.get("created", "")),
                note=str(data.get("note", "")),
                path=str(path),
            )
        )
    return out


def load_setup(car_name: str, name: str) -> dict:
    path = _car_dir("setups", car_name) / f"{_safe_name(name)}.qmsetup"
    data = _read_json(path)
    if data.get("kind") != SETUP_KIND:
        raise GarageError("El fichero no es un setup de Quick Mechanic")
    return _validate_snapshot(data.get("setup", {}), origin="El setup")


def delete_setup(car_name: str, name: str) -> bool:
    path = _car_dir("setups", car_name) / f"{_safe_name(name)}.qmsetup"
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def setup_circuits(car_name: str) -> list[str]:
    return sorted({info.circuit for info in list_setups(car_name) if info.circuit}, key=str.casefold)


def export_setup(car_name: str, name: str, path: str | Path) -> Path:
    """Copia un setup a un ``.qmsetup`` suelto para compartirlo."""
    snapshot = load_setup(car_name, name)
    payload = _read_json(_car_dir("setups", car_name) / f"{_safe_name(name)}.qmsetup")
    target = Path(path)
    if target.suffix.lower() != ".qmsetup":
        target = target.with_suffix(".qmsetup")
    signed = sign_payload({**payload, "setup": snapshot})
    target.write_text(json.dumps(signed, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def import_setup(path: str | Path) -> tuple[str, dict]:
    """Lee un ``.qmsetup`` externo; devuelve (nombre, captura) sin escribir nada."""
    data = _read_json(Path(path))
    if data.get("kind") != SETUP_KIND:
        raise GarageError("El fichero no es un setup de Quick Mechanic (.qmsetup)")
    if not verify_payload(data):
        raise GarageError("El setup no está firmado por Quick Mechanic o ha sido modificado")
    snapshot = _validate_snapshot(data.get("setup", {}), origin="El setup importado")
    return str(data.get("name") or Path(path).stem), snapshot


# --------------------------------------------------------- gestor de versiones
@dataclass(frozen=True)
class VersionInfo:
    """Version guardada del coche."""

    version_id: str
    label: str
    created: str
    path: str = ""


def save_version(car_name: str, label: str, snapshot: dict) -> Path:
    safe = _safe_name(label)
    _validate_snapshot(snapshot, origin="La version")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "kind": SETUP_KIND,
        "version": VERSION,
        "car": car_name,
        "label": safe,
        "created": _stamp(),
        "setup": snapshot,
    }
    return _write_json(_car_dir("versions", car_name) / f"{stamp}_{safe}.qmsetup", payload)


def list_versions(car_name: str) -> list[VersionInfo]:
    folder = _car_dir("versions", car_name)
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob("*.qmsetup"), key=lambda item: item.name, reverse=True):
        try:
            data = _read_json(path)
        except GarageError:
            continue
        out.append(
            VersionInfo(
                version_id=path.stem,
                label=str(data.get("label") or path.stem),
                created=str(data.get("created", "")),
                path=str(path),
            )
        )
    return out


def load_version(car_name: str, version_id: str) -> dict:
    path = _car_dir("versions", car_name) / f"{_safe_name(version_id)}.qmsetup"
    data = _read_json(path)
    return _validate_snapshot(data.get("setup", {}), origin="La version")


def delete_version(car_name: str, version_id: str) -> bool:
    path = _car_dir("versions", car_name) / f"{_safe_name(version_id)}.qmsetup"
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


# ------------------------------------------------------------------ respaldos
@dataclass(frozen=True)
class BackupInfo:
    """Respaldo ZIP del coche con lo que contiene dentro."""

    path: Path
    created: str
    size: int
    members: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def data_members(self) -> tuple[str, ...]:
        return tuple(name for name in self.members if name.startswith("data/") or name == "data.acd")


def backups_dir(car_folder: str | Path) -> Path:
    return Path(car_folder) / "quickmechanic_backups"


def list_backups(car_folder: str | Path) -> list[BackupInfo]:
    folder = backups_dir(car_folder)
    if not folder.is_dir():
        return []
    out = []
    for path in folder.glob("*.zip"):
        try:
            stat = path.stat()
        except OSError:
            continue
        out.append(
            BackupInfo(
                path=path,
                created=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                size=stat.st_size,
                members=backup_members(path),
            )
        )
    return sorted(out, key=lambda item: item.created, reverse=True)


def backup_members(archive: str | Path) -> tuple[str, ...]:
    """Nombres seguros contenidos en el ZIP (sin traversal ni absolutas)."""
    path = Path(archive)
    if path.is_symlink() or not path.is_file():
        return ()
    try:
        with zipfile.ZipFile(path) as zipped:
            names = []
            for info in zipped.infolist():
                name = info.filename
                if info.is_dir() or not name:
                    continue
                if name.startswith(("/", "\\")) or ":" in name or "\\" in name:
                    continue
                if ".." in name.split("/"):
                    continue
                names.append(name)
            return tuple(names)
    except (zipfile.BadZipFile, OSError):
        return ()


def restore_member(
    archive: str | Path,
    member: str,
    target_folder: str | Path,
    *,
    backup: bool = True,
) -> Path:
    """Restaura **un solo fichero** del respaldo dentro de ``data/`` del coche.

    Antes de escribir se hace un respaldo nuevo (``backup=True``) para que
    deshacer sea tan facil como restaurar el inmediatamente anterior.
    """
    raw_archive = Path(archive)
    raw_target = Path(target_folder)
    if raw_archive.is_symlink() or raw_target.is_symlink():
        raise GarageError("Ni el respaldo ni el coche pueden ser enlaces simbolicos")
    target = raw_target.resolve()
    if not target.is_dir():
        raise GarageError("No existe la carpeta del coche")
    if raw_archive.parent.resolve() != backups_dir(target).resolve():
        raise GarageError("El respaldo debe estar dentro de quickmechanic_backups del coche")
    name = str(member).replace("\\", "/")
    parts = [part for part in name.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts) or ":" in name:
        raise GarageError("La entrada del respaldo no es una ruta valida")
    if not (parts[0] == "data" or name == "data.acd"):
        raise GarageError("Solo se pueden restaurar ficheros de data/ o data.acd")
    safe = backup_members(raw_archive)
    if name not in safe:
        raise GarageError(f"El respaldo no contiene {name}")
    destination = target.joinpath(*parts)
    if destination.exists() and destination.is_symlink():
        raise GarageError("No se sobrescribe un enlace simbolico")
    if backup:
        from . import swaps

        try:
            swaps.create_backup(target, (name,))
        except swaps.SwapError as error:
            raise GarageError(str(error)) from None
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(raw_archive) as zipped, zipped.open(name) as source:
        temporary = destination.with_name(destination.name + ".qm-tmp")
        try:
            with temporary.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            os.replace(temporary, destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise GarageError(f"No se pudo escribir {name}: {error}") from None
    return destination


def prune_backups(car_folder: str | Path, keep: int = 5) -> int:
    """Backup inteligente: conserva los ``keep`` respaldos mas nuevos."""
    keep = max(1, int(keep))
    backups = list_backups(car_folder)
    removed = 0
    for info in backups[keep:]:
        try:
            info.path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


# --------------------------------------------------------------- clonar coche
@dataclass(frozen=True)
class CloneResult:
    """Resultado de duplicar un coche."""

    folder: Path
    name: str
    files: int
    notes: tuple[str, ...] = field(default_factory=tuple)


def suggest_clone_name(source_folder: str | Path, cars_root: str | Path | None = None) -> str:
    """Nombre libre para el clon: ``<coche>_qm``, ``_qm2``..."""
    source = Path(source_folder)
    root = Path(cars_root) if cars_root else source.parent
    base = f"{source.name}_qm"
    candidate = base
    index = 2
    while (root / candidate).exists():
        candidate = f"{base}{index}"
        index += 1
        if index > 999:
            raise GarageError("No hay nombres libres para el clon")
    return candidate


def clone_car(
    source_folder: str | Path,
    cars_root: str | Path | None = None,
    new_name: str | None = None,
) -> CloneResult:
    """Duplica un coche en una carpeta nueva sin tocar la original."""
    source = Path(source_folder)
    root = Path(cars_root) if cars_root else source.parent
    if source.is_symlink() or root.is_symlink() or not source.is_dir() or not root.is_dir():
        raise GarageError("La carpeta del coche o content/cars no es valida")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_source = source.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise GarageError(f"No se pudo validar la ruta del coche: {error}") from None
    if resolved_source.parent != resolved_root:
        raise GarageError("El coche debe estar directamente dentro de content/cars")
    name = _safe_name(new_name) if new_name else suggest_clone_name(source, root)
    destination = root / name
    if destination.is_symlink() or destination.exists():
        raise GarageError(f"Ya existe {name}")
    files = 0
    try:
        # mkdir sin exist_ok reserva el nombre de forma exclusiva: una carpeta que
        # aparezca tras la comprobacion nunca se reutiliza ni se sobrescribe.
        destination.mkdir()
        for current, dirs, names in os.walk(source, followlinks=False):
            current_path = Path(current)
            if current_path.is_symlink() or getattr(current_path, "is_junction", lambda: False)():
                raise GarageError("El coche contiene una carpeta enlazada; no se puede garantizar una copia completa")
            for dirname in dirs:
                linked = current_path / dirname
                if linked.is_symlink() or getattr(linked, "is_junction", lambda: False)():
                    raise GarageError("El coche contiene una carpeta enlazada; no se puede garantizar una copia completa")
            relative = current_path.relative_to(source)
            target_dir = destination / relative
            target_dir.mkdir(parents=True, exist_ok=True)
            for filename in names:
                origin = current_path / filename
                if origin.is_symlink() or getattr(origin, "is_junction", lambda: False)():
                    raise GarageError("El coche contiene un archivo enlazado; no se puede garantizar una copia completa")
                shutil.copy2(origin, target_dir / filename)
                files += 1
    except (OSError, GarageError) as error:
        shutil.rmtree(destination, ignore_errors=True)
        if isinstance(error, GarageError):
            raise
        raise GarageError(f"No se pudo clonar el coche: {error}") from None
    notes = [
        "El clon es una copia independiente: editar aqui no toca el coche original.",
        "Recuerda cambiarle el nombre visible en ui/ui_car.json para no confundirlos en AC.",
    ]
    return CloneResult(destination, name, files, tuple(notes))
