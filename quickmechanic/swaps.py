"""Validated, one-way component transfers between editable Assetto Corsa cars.

Donor files are only read. A timestamped archive of the target's extracted data
(and every other file about to be replaced) is made before any target write.
The proprietary ``data.acd`` is archived when present, never unpacked or edited.
"""
from __future__ import annotations

import math
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from .car_data import CarData
from .ini_editor import ACIni
from .lut import LUT

__all__ = ["SwapError", "SwapPlan", "prepare_swap", "apply_swap", "create_backup", "restore_backup"]


class SwapError(ValueError):
    """A donor/target pair is incomplete or incompatible for the requested swap."""


@dataclass(frozen=True)
class SwapPlan:
    kind: str
    donor: Path
    target: Path
    copies: dict[str, Path] = field(default_factory=dict)
    ini_updates: dict[str, tuple[tuple[str, str, str], ...]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.copies) | set(self.ini_updates)))


def _local_data_file(data_dir: Path, reference: str, label: str) -> Path:
    """Only allow a plain filename within data/; reject paths and traversal."""
    name = reference.strip().replace("\\", "/")
    if not name or name in {"FROM_COAST_REF", "FROM_COAST"}:
        raise SwapError(f"Referencia {label} vacía o no compatible: {reference!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or len(path.parts) != 1 or path.name in {".", ".."}:
        raise SwapError(f"La referencia {label} debe ser un archivo local de data/: {reference}")
    if path.suffix.casefold() != ".lut":
        raise SwapError(f"La referencia {label} debe apuntar a un archivo .lut: {reference}")
    result = data_dir / path.name
    try:
        result.resolve().relative_to(data_dir.resolve())
    except ValueError as error:
        raise SwapError(f"La referencia {label} sale de data/: {reference}") from error
    if result.is_symlink() or not result.is_file():
        raise SwapError(f"Falta el archivo local no enlazado de {label} del donante: {result.name}")
    return result


def _sound_file(car_folder: Path, reference: str, suffix: str) -> tuple[str, Path]:
    """Resolve a bank/GUID path either at car root or inside its sfx directory."""
    text = reference.strip().replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise SwapError(f"Ruta de sonido no válida: {reference}")
    if not path.name.lower().endswith(suffix):
        raise SwapError(f"Ruta de sonido no válida: {reference}")
    if len(path.parts) == 1:
        relative = path.name
    elif len(path.parts) >= 2 and path.parts[0].casefold() == "sfx":
        relative = path.as_posix()
    else:
        raise SwapError(f"Los archivos de sonido deben estar en la raíz del coche o sfx/: {reference}")
    source = car_folder.joinpath(*PurePosixPath(relative).parts)
    try:
        source.resolve().relative_to(car_folder.resolve())
    except ValueError as error:
        raise SwapError(f"La ruta de sonido sale de la carpeta del coche: {reference}") from error
    if source.is_symlink() or not source.is_file():
        raise SwapError(f"Falta el archivo local no enlazado de sonido del donante: {reference}")
    if len(source.resolve().relative_to(car_folder.resolve()).parts) != len(PurePosixPath(relative).parts):
        raise SwapError(f"El archivo de sonido usa una ruta simbólica no permitida: {reference}")
    return relative, source


def _sound_swap(donor: Path, target: Path) -> SwapPlan:
    donor_ini = donor / "sfx.ini"
    if donor_ini.is_symlink():
        raise SwapError("No se utiliza un sfx.ini simbólico como donante.")
    if not donor_ini.is_file():
        raise SwapError("El coche donante no tiene sfx.ini en la raíz.")
    ini = ACIni(donor_ini)
    sections = [name for name in ini.sections() if name.upper().startswith("SOUNDBANK_")]
    if not sections:
        raise SwapError("sfx.ini no declara ninguna sección [SOUNDBANK_n].")

    copies: dict[str, Path] = {"sfx.ini": donor_ini}
    bank_count = 0
    for section in sections:
        bank = ini.get(section, "BANK", "").strip()
        guids = ini.get(section, "GUIDS", "").strip()
        if not bank or not guids:
            raise SwapError(f"[{section}] debe declarar BANK y GUIDS.")
        bank_rel, bank_path = _sound_file(donor, bank, ".bank")
        guid_rel, guid_path = _sound_file(donor, guids, ".txt")
        if bank_path.stat().st_size == 0 or guid_path.stat().st_size == 0:
            raise SwapError(f"[{section}] referencia un banco o GUIDs.txt vacío.")
        if any("\\n" in name or "\\r" in name for name in (bank_rel, guid_rel)):
            raise SwapError(f"[{section}] tiene rutas de archivo con saltos de línea.")
        copies[bank_rel] = bank_path
        copies[guid_rel] = guid_path
        bank_count += 1
    return SwapPlan(
        "sonido", donor, target, copies,
        warnings=(
            f"Se copiarán sfx.ini, {bank_count} banco(s) declarado(s) y sus GUIDs.txt.",
            "Los archivos de sonido antiguos no referenciados se conservarán; no se borra nada.",
        ),
    )


def _engine_swap(donor: Path, target: Path) -> SwapPlan:
    source_data = donor / "data"
    source_ini_path = source_data / "engine.ini"
    target_ini_path = target / "data" / "engine.ini"
    if source_ini_path.is_symlink() or target_ini_path.is_symlink():
        raise SwapError("No se utilizan engine.ini simbólicos en los intercambios de motor.")
    if not source_ini_path.is_file() or not target_ini_path.is_file():
        raise SwapError("Donante y destino necesitan una carpeta data/ con engine.ini extraído.")
    engine = ACIni(source_ini_path)
    limiter = engine.get_float("ENGINE_DATA", "LIMITER", -1)
    inertia = engine.get_float("ENGINE_DATA", "INERTIA", -1)
    if (
        not engine.has_section("ENGINE_DATA")
        or not math.isfinite(limiter)
        or not math.isfinite(inertia)
        or limiter <= 0
        or inertia <= 0
    ):
        raise SwapError("engine.ini del donante no contiene datos básicos de motor válidos.")

    power_ref = engine.get("HEADER", "POWER_CURVE", "power.lut").strip() or "power.lut"
    power_path = _local_data_file(source_data, power_ref, "POWER_CURVE")
    power_lut = LUT(power_path)
    if power_lut.n_rows < 2 or power_lut.n_cols < 2:
        raise SwapError("La curva de potencia del donante necesita al menos dos puntos válidos.")
    rpms = [row[0] for row in power_lut.rows]
    if any(not all(math.isfinite(value) for value in row) for row in power_lut.rows):
        raise SwapError("La curva de potencia contiene valores no finitos.")
    if any(right <= left for left, right in zip(rpms, rpms[1:])):
        raise SwapError("Las RPM de power.lut deben aumentar estrictamente.")
    if rpms[-1] < limiter:
        raise SwapError(
            f"El limitador ({limiter:g} RPM) supera el último punto de la curva ({rpms[-1]:g} RPM)."
        )

    rpm_damage_limit = engine.get_float("DAMAGE", "RPM_THRESHOLD", 0.0)
    turbo_maxima = [
        engine.get_float(section, "MAX_BOOST", 0.0)
        for section in engine.sections()
        if section.upper().startswith("TURBO_") and engine.has(section, "MAX_BOOST")
    ]
    if any(not math.isfinite(value) or value < 0 for value in turbo_maxima):
        raise SwapError("El donante contiene un valor MAX_BOOST no válido.")
    total_boost = sum(turbo_maxima)
    turbo_damage_limit = engine.get_float("DAMAGE", "TURBO_BOOST_THRESHOLD", 0.0)

    copies = {"data/engine.ini": source_ini_path, f"data/{power_path.name}": power_path}
    coast_ref = engine.get("HEADER", "COAST_CURVE", "").strip()
    if coast_ref.upper() in {"FROM_COAST_REF", "FROM_COAST"}:
        coast_data = {key.upper(): value for key, value in engine.section("COAST_REF").items()}
        try:
            coast_rpm = float(coast_data.get("RPM", "nan"))
            coast_torque = float(coast_data.get("TORQUE", "nan"))
        except ValueError as error:
            raise SwapError("El donante usa COAST_REF, pero RPM/TORQUE no son numéricos.") from error
        if not math.isfinite(coast_rpm) or coast_rpm <= 0 or not math.isfinite(coast_torque):
            raise SwapError("El donante usa COAST_REF, pero RPM/TORQUE no son válidos.")
    if coast_ref and coast_ref.upper() not in {"FROM_COAST_REF", "FROM_COAST"}:
        coast_path = _local_data_file(source_data, coast_ref, "COAST_CURVE")
        coast_lut = LUT(coast_path)
        if coast_lut.n_rows < 2 or coast_lut.n_cols < 2:
            raise SwapError("La curva de freno motor del donante está vacía o incompleta.")
        copies[f"data/{coast_path.name}"] = coast_path

    warnings = [
        f"Motor del donante: limitador {limiter:g} RPM; se transfiere su curva y turbo tal cual.",
        "El coche original del donante no se modifica. La caja, masa y chasis del destino se conservan.",
        "La compatibilidad mecánica no se puede garantizar por software: prueba el coche en pista.",
    ]
    if rpm_damage_limit > 0 and rpm_damage_limit < limiter:
        warnings.append(
            f"El umbral de daño RPM ({rpm_damage_limit:g}) está por debajo del limitador ({limiter:g}); "
            "se conserva exactamente como en el coche donante."
        )
    if turbo_damage_limit > 0 and total_boost > turbo_damage_limit:
        warnings.append(
            f"El boost máximo calculado ({total_boost:g}) supera el umbral de daño turbo "
            f"({turbo_damage_limit:g}); se conserva sin cambios."
        )
    try:
        source_power = CarData(source_data, name=donor.name).peak_power()[1]
        target_power = CarData(target / "data", name=target.name).peak_power()[1]
        if source_power and target_power and source_power > target_power * 1.5:
            warnings.append(
                f"Aviso: el motor donante calcula {source_power:.0f} CV frente a {target_power:.0f} CV del destino."
            )
    except (OSError, ValueError, IndexError):
        pass
    return SwapPlan("motor", donor, target, copies, warnings=tuple(warnings))


def _section_updates(
    source: ACIni, target: ACIni, section: str, keys: tuple[str, ...]
) -> list[tuple[str, str, str]]:
    if not source.has_section(section) or not target.has_section(section):
        return []
    changes = []
    for key in keys:
        if source.has(section, key) and target.has(section, key):
            changes.append((section, key, source.get(section, key)))
    return changes


def _transmission_swap(donor: Path, target: Path) -> SwapPlan:
    source_path = donor / "data" / "drivetrain.ini"
    target_path = target / "data" / "drivetrain.ini"
    if source_path.is_symlink() or target_path.is_symlink():
        raise SwapError("No se utilizan drivetrain.ini simbólicos en el intercambio.")
    if not source_path.is_file() or not target_path.is_file():
        raise SwapError("Ambos coches necesitan data/drivetrain.ini extraído.")
    source, current = ACIni(source_path), ACIni(target_path)
    source_type = source.get("TRACTION", "TYPE", "RWD").strip().upper() or "RWD"
    target_type = current.get("TRACTION", "TYPE", "RWD").strip().upper() or "RWD"
    allowed_types = {"FWD", "RWD", "4WD", "AWD"}
    if source_type not in allowed_types or target_type not in allowed_types:
        raise SwapError(f"Tipo de tracción no reconocido ({source_type} / {target_type}).")
    if source_type != target_type:
        raise SwapError(
            f"Tracción incompatible ({source_type} → {target_type}). La conversión FWD/RWD/AWD no se hace automáticamente."
        )
    count = source.get_int("GEARS", "COUNT", 0)
    target_count = current.get_int("GEARS", "COUNT", 0)
    if not 1 <= count <= 12 or not 1 <= target_count <= 12:
        raise SwapError("El número de marchas debe estar entre 1 y 12 en ambos coches.")
    gear_keys = tuple(["COUNT", "GEAR_R", "FINAL"] + [f"GEAR_{index}" for index in range(1, count + 1)])
    missing = [key for key in gear_keys if not source.has("GEARS", key)]
    if missing:
        raise SwapError("El donante no declara todas las marchas indicadas en COUNT: " + ", ".join(missing))
    if not current.has_section("GEARS"):
        raise SwapError("El destino no tiene una sección [GEARS] que se pueda adaptar.")
    updates = [("GEARS", key, source.get("GEARS", key)) for key in gear_keys]
    try:
        reverse_ratio = float(source.get("GEARS", "GEAR_R"))
        final_drive = float(source.get("GEARS", "FINAL"))
    except ValueError as error:
        raise SwapError("La marcha atrás y el grupo final deben ser valores numéricos.") from error
    if not math.isfinite(reverse_ratio) or reverse_ratio >= 0:
        raise SwapError("La relación de marcha atrás del donante debe ser negativa.")
    if not math.isfinite(final_drive) or final_drive <= 0:
        raise SwapError("El grupo final del donante debe ser positivo.")
    for key in gear_keys[3:]:
        try:
            ratio = float(source.get("GEARS", key))
        except ValueError as error:
            raise SwapError(f"Relación de marcha no numérica: {key}={source.get('GEARS', key)}") from error
        if not math.isfinite(ratio) or ratio <= 0:
            raise SwapError(f"Relación de marcha no válida: {key}={ratio}")
    updates += _section_updates(source, current, "DIFFERENTIAL", ("POWER", "COAST", "PRELOAD"))
    updates += _section_updates(
        source, current, "GEARBOX",
        ("CHANGE_UP_TIME", "CHANGE_DN_TIME", "SUPPORTS_SHIFTER", "AUTO_CUTOFF", "AUTO_BLIP"),
    )
    updates += _section_updates(source, current, "CLUTCH", ("MAX_TORQUE",))
    if not updates:
        raise SwapError("No se encontraron parámetros de transmisión compatibles.")
    missing_optional = []
    for section, keys in (
        ("DIFFERENTIAL", ("POWER", "COAST", "PRELOAD")),
        ("GEARBOX", ("CHANGE_UP_TIME", "CHANGE_DN_TIME", "SUPPORTS_SHIFTER")),
        ("CLUTCH", ("MAX_TORQUE",)),
    ):
        for key in keys:
            if source.has(section, key) and not current.has(section, key):
                missing_optional.append(f"{section}.{key}")
    warnings = [f"Se mantiene el tipo de tracción {target_type}; se copian relaciones y parámetros presentes en ambos coches."]
    if count != target_count:
        warnings.append(f"El número de marchas cambiará de {target_count} a {count}.")
    if missing_optional:
        warnings.append("Parámetros no soportados por el destino: " + ", ".join(missing_optional))
    return SwapPlan(
        "transmisión", donor, target,
        ini_updates={"data/drivetrain.ini": tuple(updates)},
        warnings=tuple(warnings),
    )


def _suspension_swap(donor: Path, target: Path) -> SwapPlan:
    source_path = donor / "data" / "suspensions.ini"
    target_path = target / "data" / "suspensions.ini"
    if source_path.is_symlink() or target_path.is_symlink():
        raise SwapError("No se utilizan suspensions.ini simbólicos en el intercambio.")
    if not source_path.is_file() or not target_path.is_file():
        raise SwapError("Ambos coches necesitan data/suspensions.ini extraído.")
    source, current = ACIni(source_path), ACIni(target_path)
    keys = ("BASEY", "ROD_LENGTH", "TRACK", "STATIC_CAMBER", "TOE_OUT")
    updates = []
    for section in ("FRONT", "REAR"):
        if not source.has_section(section) or not current.has_section(section):
            raise SwapError(f"Falta la sección [{section}] en la suspensión de un coche.")
        updates += _section_updates(source, current, section, keys)
    if not updates:
        raise SwapError("No hay parámetros de altura/alineación compatibles que copiar.")
    for section, key, text in updates:
        try:
            value = float(text)
        except ValueError as error:
            raise SwapError(f"Valor no numérico en [{section}] {key}={text}.") from error
        limits = {"TRACK": (0.8, 2.5), "BASEY": (-1.0, 0.5), "ROD_LENGTH": (-1.0, 1.0),
                  "STATIC_CAMBER": (-30.0, 30.0), "TOE_OUT": (-0.2, 0.2)}
        low, high = limits[key]
        if not math.isfinite(value) or not low <= value <= high:
            raise SwapError(f"Valor extremo o no numérico en [{section}] {key}={text}.")
    return SwapPlan(
        "fitment", donor, target,
        ini_updates={"data/suspensions.ini": tuple(updates)},
        warnings=(
            "Solo se copian altura geométrica, vías, caída y convergencia ya declaradas; muelles y amortiguadores del destino se conservan.",
            "Revisa colisiones, neumáticos y comportamiento en pista antes de conducir.",
        ),
    )


def prepare_swap(kind: str, donor_folder: str | Path, target_folder: str | Path) -> SwapPlan:
    """Validate a donor and return a preview; this function never writes files."""
    donor_input = Path(donor_folder)
    target_input = Path(target_folder)
    if donor_input.is_symlink() or target_input.is_symlink():
        raise SwapError("No se preparan swaps usando carpetas de coche simbólicas.")
    donor = donor_input.resolve()
    target = target_input.resolve()
    if not donor.is_dir() or not target.is_dir():
        raise SwapError("Donante y destino deben ser carpetas de coche existentes.")
    if donor == target:
        raise SwapError("El coche donante y el coche destino deben ser distintos.")
    kind = kind.strip().casefold()
    if kind == "motor":
        return _engine_swap(donor, target)
    if kind in {"transmisión", "transmision", "transmission"}:
        return _transmission_swap(donor, target)
    if kind in {"fitment", "suspensión", "suspension"}:
        return _suspension_swap(donor, target)
    if kind in {"sonido", "sound"}:
        return _sound_swap(donor, target)
    raise SwapError(f"Tipo de intercambio desconocido: {kind}")


def _backup_target(target: Path, destinations: tuple[str, ...] = ()) -> Path:
    if target.is_symlink() or not target.is_dir():
        raise SwapError(f"No existe una carpeta de coche destino segura: {target}")
    backup_dir = target / "quickmechanic_backups"
    if backup_dir.is_symlink():
        raise SwapError("Por seguridad no se escribe dentro de una carpeta de respaldos simbólica.")
    backup_dir.mkdir(parents=True, exist_ok=True)
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise SwapError("La ubicación de respaldos no es una carpeta local segura.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    archive = backup_dir / f"data_backup_{stamp}.zip"
    files: set[Path] = set()
    data_dir = target / "data"
    if data_dir.is_symlink():
        raise SwapError("Por seguridad no se respalda a través de una carpeta data/ simbólica.")
    if data_dir.is_dir():
        for path in data_dir.rglob("*"):
            if path.is_symlink():
                raise SwapError(f"No se puede respaldar data/ porque contiene un enlace simbólico: {path.name}")
            if path.is_file() and not path.name.endswith(".qm-tmp"):
                files.add(path)
    acd = target / "data.acd"
    if acd.is_symlink():
        raise SwapError("Por seguridad no se respalda un data.acd que sea un enlace simbólico.")
    if acd.is_file():
        files.add(acd)
    is_sound_backup = any(
        relative == "sfx.ini"
        or relative.startswith("sfx/")
        or Path(relative).suffix.casefold() in {".bank", ".txt"}
        for relative in destinations
    )
    if is_sound_backup:
        sfx_dir = target / "sfx"
        if sfx_dir.is_symlink():
            raise SwapError("Por seguridad no se respalda a través de una carpeta sfx/ simbólica.")
        if sfx_dir.is_dir():
            for path in sfx_dir.rglob("*"):
                if path.is_symlink():
                    raise SwapError(f"No se puede respaldar sfx/ porque contiene un enlace simbólico: {path.name}")
                if path.is_file():
                    files.add(path)
        sfx_ini = target / "sfx.ini"
        if sfx_ini.is_symlink():
            raise SwapError("Por seguridad no se respalda un sfx.ini simbólico.")
        if sfx_ini.is_file():
            files.add(sfx_ini)
        for child in target.iterdir():
            if child.is_symlink() and child.suffix.casefold() in {".bank", ".txt"}:
                raise SwapError(f"No se puede respaldar un archivo de sonido enlazado simbólicamente: {child.name}")
            if child.is_file() and child.suffix.casefold() in {".bank", ".txt"}:
                files.add(child)
    for relative in destinations:
        safe = PurePosixPath(relative)
        if (
            safe.is_absolute()
            or not safe.parts
            or any(part in {".", ".."} for part in safe.parts)
            or "\\" in relative
            or ":" in relative
            or any(part.endswith((".", " ")) for part in safe.parts)
        ):
            raise SwapError(f"Ruta de respaldo no permitida: {relative}")
        path = target.joinpath(*safe.parts)
        if path.is_file() and not path.is_symlink():
            files.add(path)
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(files):
                try:
                    arcname = path.relative_to(target).as_posix()
                except ValueError as error:
                    raise SwapError(f"No se puede respaldar una ruta externa: {path}") from error
                zipped.write(path, arcname)
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    return archive


def create_backup(
    target_folder: str | Path,
    destinations: tuple[str, ...] = (),
) -> Path:
    """Create a timestamped snapshot of extracted data, data.acd and selected files."""
    target = Path(target_folder)
    if target.is_symlink():
        raise SwapError("No se crea un respaldo a través de una carpeta de coche simbólica.")
    return _backup_target(target.resolve(), destinations)


def restore_backup(target_folder: str | Path, archive_path: str | Path) -> Path:
    """Safely restore only data/ and data.acd entries from a Quick Mechanic archive.

    A fresh backup is created first. The routine does not extract arbitrary paths,
    overwrite symlinks, or delete files absent from the archive.
    """
    raw_target = Path(target_folder)
    raw_archive = Path(archive_path)
    if raw_target.is_symlink() or raw_archive.is_symlink():
        raise SwapError("No se restaura desde un respaldo o destino que sea un enlace simbólico.")
    target = raw_target.resolve()
    archive = raw_archive.resolve()
    if not target.is_dir() or not archive.is_file():
        raise SwapError("No se encontró la carpeta de destino o el archivo ZIP seleccionado.")
    if archive.parent != target / "quickmechanic_backups":
        raise SwapError("El respaldo debe estar directamente dentro de quickmechanic_backups del coche seleccionado.")
    staged: list[tuple[str, Path, Path]] = []
    committed: list[str] = []
    safety: Path | None = None
    try:
        with zipfile.ZipFile(archive, "r") as zipped:
            names = zipped.namelist()
            if not names:
                raise SwapError("El archivo de respaldo está vacío.")
            seen: set[str] = set()
            for info in zipped.infolist():
                path = PurePosixPath(info.filename)
                if (
                    not path.parts
                    or path.is_absolute()
                    or any(part in {".", ".."} for part in path.parts)
                    or "\\" in info.filename
                    or ":" in info.filename
                    or any(character in info.filename for character in ("\x00", "\n", "\r"))
                    or any(part.endswith((".", " ")) for part in path.parts)
                    or not (
                        path.parts[0] == "data"
                        or path.as_posix() == "data.acd"
                        or path.as_posix() == "sfx.ini"
                        or path.parts[0] == "sfx"
                        or (len(path.parts) == 1 and path.suffix.casefold() in {".bank", ".txt"})
                    )
                ):
                    raise SwapError(f"Ruta no permitida dentro del respaldo: {info.filename}")
                if path.as_posix() in seen:
                    raise SwapError(f"El respaldo repite una ruta: {info.filename}")
                seen.add(path.as_posix())
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode and (mode & 0o170000) == 0o120000:
                    raise SwapError(f"El respaldo contiene un enlace simbólico: {info.filename}")
                if info.is_dir():
                    continue
                destination = target.joinpath(*path.parts)
                try:
                    destination.resolve(strict=False).relative_to(target)
                except ValueError as error:
                    raise SwapError(f"Ruta restaurada fuera de la carpeta del coche: {info.filename}") from error
                parent = target
                for part in path.parts[:-1]:
                    parent = parent / part
                    if parent.is_symlink():
                        raise SwapError(f"No se restaura a través de un enlace simbólico: {info.filename}")
                    if parent.exists() and not parent.is_dir():
                        raise SwapError(f"La ruta restaurada no es una carpeta: {info.filename}")
                if not path.parts[-1].casefold().endswith(
                    (".ini", ".lut", ".rto", ".acd", ".bank", ".txt", ".bak", ".json", ".bin")
                ):
                    raise SwapError(f"Extensión no permitida en el respaldo: {info.filename}")
            if destination.is_symlink():
                raise SwapError(f"No se restaura sobre un enlace simbólico: {info.filename}")
            if destination.exists() and not destination.is_file():
                raise SwapError(f"La ruta destino no es un archivo: {info.filename}")
            total_size = sum(info.file_size for info in zipped.infolist())
            if len(seen) > 10000 or total_size > 2 * 1024 * 1024 * 1024:
                raise SwapError("El respaldo supera los límites de tamaño o número de archivos permitidos.")
            safety = _backup_target(target, tuple(seen))
            for info in zipped.infolist():
                if info.is_dir():
                    continue
                destination = target.joinpath(*PurePosixPath(info.filename).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                descriptor, raw_temp = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".qm-restore", dir=destination.parent)
                os.close(descriptor)
                temporary = Path(raw_temp)
                staged.append((info.filename, destination, temporary))
                with zipped.open(info, "r") as source, temporary.open("wb") as output:
                    shutil.copyfileobj(source, output)
        for relative, destination, temporary in staged:
            os.replace(temporary, destination)
            committed.append(relative)
        return safety
    except Exception as error:
        if safety is not None:
            for relative in reversed(committed):
                try:
                    _restore_committed(safety, target, relative)
                except OSError:
                    pass
        if isinstance(error, SwapError):
            raise
        raise SwapError(f"No se pudo restaurar el respaldo: {error}") from error
    finally:
        for _relative, _destination, temporary in staged:
            temporary.unlink(missing_ok=True)


def _stage(
    destination: Path,
    source: Path | None,
    updates: tuple[tuple[str, str, str], ...] | None,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".qm-tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(raw_temp)
    try:
        if updates is not None:
            if source is not None:
                shutil.copy2(source, temporary)
            elif destination.is_file():
                shutil.copy2(destination, temporary)
            else:
                raise SwapError(f"No existe el archivo base que se iba a editar: {destination}")
            ini = ACIni(temporary)
            for section, key, value in updates:
                ini.set_value(section, key, value)
            ini.save(backup=False)
        elif source is not None:
            shutil.copy2(source, temporary)
        else:
            raise SwapError("El plan de intercambio no tiene contenido para escribir.")
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        temporary.with_name(temporary.name + ".tmp").unlink(missing_ok=True)
        raise


def _restore_committed(archive: Path, target: Path, relative: str) -> None:
    destination = target.joinpath(*PurePosixPath(relative).parts)
    with zipfile.ZipFile(archive, "r") as zipped:
        try:
            source = zipped.open(relative)
        except KeyError:
            destination.unlink(missing_ok=True)
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_temp = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".qm-restore", dir=destination.parent)
        os.close(descriptor)
        temporary = Path(raw_temp)
        try:
            with source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def apply_swap(plan: SwapPlan) -> Path:
    """Archive first, stage all writes, then atomically replace every target file."""
    if plan.target.is_symlink() or plan.donor.is_symlink():
        raise SwapError("No se aplican swaps a través de carpetas simbólicas.")
    target = plan.target.resolve()
    if not target.is_dir() or not plan.donor.is_dir():
        raise SwapError("El coche donante o destino dejó de existir.")
    if plan.donor.resolve() == target:
        raise SwapError("El coche donante no puede ser el coche destino.")
    destinations = plan.files
    if not destinations:
        raise SwapError("El plan de intercambio está vacío.")

    staged: list[tuple[str, Path, Path]] = []
    committed: list[str] = []
    archive: Path | None = None
    originals = {
        relative: target.joinpath(*PurePosixPath(relative).parts).is_file()
        for relative in destinations
    }
    try:
        if target.is_symlink() or plan.donor.is_symlink():
            raise SwapError("No se aplican swaps a través de carpetas simbólicas.")
        for relative in destinations:
            safe_relative = PurePosixPath(relative)
            if (
                safe_relative.is_absolute()
                or any(part in {".", ".."} for part in safe_relative.parts)
                or not safe_relative.parts
                or not (
                    safe_relative.parts[0] == "data"
                    or relative == "sfx.ini"
                    or safe_relative.parts[0] == "sfx"
                    or (
                        plan.kind == "sonido"
                        and len(safe_relative.parts) == 1
                        and safe_relative.suffix.casefold() in {".bank", ".txt"}
                    )
                )
            ):
                raise SwapError(f"Ruta de destino no permitida: {relative}")
            destination = target.joinpath(*safe_relative.parts)
            parent = target
        for part in safe_relative.parts[:-1]:
            parent = parent / part
            if parent.exists() and not parent.is_dir():
                raise SwapError(f"La ruta destino no es una carpeta: {relative}")
            if parent.is_symlink():
                raise SwapError(f"Por seguridad no se escribe a través de enlaces simbólicos: {relative}")
            if destination.is_symlink():
                raise SwapError(f"Por seguridad no se sobrescribe un enlace simbólico: {relative}")
            if destination.exists() and not destination.is_file():
                raise SwapError(f"La ruta destino no es un archivo: {relative}")
            source_file = plan.copies.get(relative)
            if source_file is not None:
                try:
                    source_file.resolve().relative_to(plan.donor.resolve())
                except ValueError as error:
                    raise SwapError(f"El origen de copia sale de la carpeta donante: {source_file}") from error
        archive = _backup_target(target, destinations)
        for relative, destination_exists in originals.items():
            if destination_exists:
                destination = target.joinpath(*PurePosixPath(relative).parts)
                backup_file = destination.with_name(destination.name + ".bak")
                if not backup_file.exists():
                    shutil.copy2(destination, backup_file)
        for relative in destinations:
            destination = target.joinpath(*PurePosixPath(relative).parts)
            source_file = plan.copies.get(relative)
            if source_file is not None and (source_file.is_symlink() or not source_file.is_file()):
                raise SwapError(f"El archivo del donante ya no está disponible: {source_file.name}")
            updates = plan.ini_updates.get(relative)
            source = plan.copies.get(relative)
            staged_file = _stage(destination, source, updates)
            staged.append((relative, destination, staged_file))
        for relative, destination, temporary in staged:
            os.replace(temporary, destination)
            committed.append(relative)
        return archive
    except Exception as error:
        if archive is not None:
            for relative in reversed(committed):
                try:
                    _restore_committed(archive, target, relative)
                except OSError:
                    pass
        if isinstance(error, SwapError):
            raise
        raise SwapError(f"No se pudo aplicar el intercambio: {error}") from error
    finally:
        for _relative, _destination, temporary in staged:
            temporary.unlink(missing_ok=True)
            temporary.with_name(temporary.name + ".tmp").unlink(missing_ok=True)
