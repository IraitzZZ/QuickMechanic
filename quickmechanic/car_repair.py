"""Diagnóstico y reparación de datos de coches de Assetto Corsa.

Portado de AcManager.ContentRepair (Ms-PL, © gro-ove, ver LICENSE de actools):
- car.ini [HEADER] VERSION no válida.
- aero.ini con la sección [DATA] obsoleta.
- aero.ini con LUT de alas inexistentes o vacíos.

Reglas de seguridad:
- diagnose() solo lee: sirve de vista previa de lo que cambiaría.
- repair() exige confirmed=True y, antes de tocar nada, copia cada archivo
  afectado a <archivo>.<fecha-hora>.bak (nunca sobrescribe copias anteriores).
- Los nombres de LUT deben ser un nombre de archivo simple dentro de data/.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .ac_ini import IniParser
from .ac_lut import LUTCurve

CAR_INI = "car.ini"
AERO_INI = "aero.ini"

CODE_CAR_VERSION = "car_ini_version"
CODE_AERO_DATA = "aero_data_obsolete"
CODE_AERO_LUT = "aero_lut_empty"
ALL_CODES = (CODE_CAR_VERSION, CODE_AERO_DATA, CODE_AERO_LUT)

EXPECTED_CAR_VERSION = 2


@dataclass(frozen=True)
class Issue:
    code: str
    title: str
    detail: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class RepairResult:
    applied: tuple[str, ...]
    changed_files: tuple[str, ...]
    backups: tuple[Path, ...]
    remaining: tuple[Issue, ...]


def _data_dir(car_dir: str | Path) -> Path:
    car = Path(car_dir)
    data = car / "data"
    if not car.is_dir() or not (data / CAR_INI).is_file():
        raise ValueError(f"No es una carpeta de coche válida (falta data/{CAR_INI}): {car}")
    return data


def _validate_codes(codes: Optional[Iterable[str]]) -> set[str]:
    if codes is None:
        return set(ALL_CODES)
    selected = set(codes)
    unknown = selected - set(ALL_CODES)
    if unknown:
        raise ValueError(f"Reparación desconocida: {', '.join(sorted(unknown))}")
    return selected


def _version_ok(value: Optional[str]) -> bool:
    if value is None or not value.strip():
        return False
    text = value.strip()
    if text.startswith("extended-"):
        return True
    try:
        number = int(text)
    except ValueError:
        return False
    return 0 < number < 10


def _is_inline_lut(value: str) -> bool:
    # Igual que Lut.IsInlineValue de AcTools: valores tipo "0=0.8|1000=0.9" no son archivos.
    return not value.lower().endswith(".lut") and ("=" in value or "|" in value)


def _wing_sections(aero: IniParser) -> list[str]:
    return [s for s in aero.config.sections() if s.startswith("WING")]


def _missing_wing_luts(data: Path, aero: IniParser) -> list[str]:
    names: list[str] = []
    for section in _wing_sections(aero):
        for key in ("LUT_AOA_CD", "LUT_AOA_CL"):
            raw = aero.get_value(section, key)
            if raw is None or not raw.strip():
                continue
            name = raw.strip()
            if _is_inline_lut(name):
                continue
            if Path(name).name != name:
                continue  # rutas fuera de data/ no se tocan nunca
            path = data / name
            if path.is_file() and len(LUTCurve(str(path))) > 0:
                continue
            if name not in names:
                names.append(name)
    return names


def diagnose(car_dir: str | Path, codes: Optional[Iterable[str]] = None) -> list[Issue]:
    """Devuelve los problemas encontrados sin modificar ningún archivo."""
    data = _data_dir(car_dir)
    wanted = _validate_codes(codes)
    issues: list[Issue] = []

    if CODE_CAR_VERSION in wanted:
        car = IniParser(str(data / CAR_INI))
        value = car.get_value("HEADER", "VERSION")
        if not _version_ok(value):
            issues.append(Issue(
                CODE_CAR_VERSION,
                "VERSION no válida en car.ini",
                f"[HEADER] VERSION actual: {value or '(vacía)'}. Se pondrá {EXPECTED_CAR_VERSION}.",
                (CAR_INI,),
            ))

    aero_path = data / AERO_INI
    if aero_path.is_file() and wanted & {CODE_AERO_DATA, CODE_AERO_LUT}:
        aero = IniParser(str(aero_path))
        if CODE_AERO_DATA in wanted and aero.has_section("DATA"):
            issues.append(Issue(
                CODE_AERO_DATA,
                "Sección [DATA] obsoleta en aero.ini",
                "Esa sección ya no la usa Assetto Corsa. Se eliminará.",
                (AERO_INI,),
            ))
        if CODE_AERO_LUT in wanted:
            luts = _missing_wing_luts(data, aero)
            if luts:
                issues.append(Issue(
                    CODE_AERO_LUT,
                    "LUT de alas vacíos o inexistentes",
                    "Se crearán con un punto (0|0): " + ", ".join(luts) + ". "
                    "Sin ellos, AC escribe muchas líneas en el log.",
                    tuple(luts),
                ))
    return issues


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = path.with_name(f"{path.name}.{stamp}.bak")
    counter = 1
    while target.exists():  # nunca sobrescribir una copia anterior
        target = path.with_name(f"{path.name}.{stamp}-{counter}.bak")
        counter += 1
    shutil.copy2(path, target)
    return target


def repair(
    car_dir: str | Path,
    codes: Optional[Iterable[str]] = None,
    *,
    confirmed: bool = False,
) -> RepairResult:
    """Aplica las reparaciones seleccionadas. Requiere confirmed=True."""
    if not confirmed:
        raise PermissionError("La reparación necesita confirmación explícita.")
    data = _data_dir(car_dir)
    wanted = _validate_codes(codes)
    issues = {issue.code: issue for issue in diagnose(car_dir, wanted)}
    if not issues:
        return RepairResult((), (), (), ())

    # Copias de seguridad de todo lo que se va a tocar, antes de escribir nada.
    touched = sorted({name for issue in issues.values() for name in issue.files})
    backups = tuple(_backup(data / name) for name in touched if (data / name).is_file())

    applied: list[str] = []
    changed: list[str] = []

    if CODE_CAR_VERSION in issues:
        car = IniParser(str(data / CAR_INI))
        car.set_value("HEADER", "VERSION", EXPECTED_CAR_VERSION)
        car.save(backup=False)
        applied.append(CODE_CAR_VERSION)
        changed.append(CAR_INI)

    if CODE_AERO_DATA in issues:
        aero = IniParser(str(data / AERO_INI))
        aero.remove_section("DATA")
        aero.save(backup=False)
        applied.append(CODE_AERO_DATA)
        changed.append(AERO_INI)

    if CODE_AERO_LUT in issues:
        for name in issues[CODE_AERO_LUT].files:
            lut = LUTCurve()
            lut.points = [(0.0, 0.0)]
            lut.save(str(data / name), backup=False)
            changed.append(name)
        applied.append(CODE_AERO_LUT)

    # Todo lo que sigue mal, incluidos los problemas que no se han seleccionado.
    remaining = tuple(diagnose(car_dir))
    return RepairResult(tuple(applied), tuple(changed), backups, remaining)
