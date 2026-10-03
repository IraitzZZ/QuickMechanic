"""Capa de datos de un coche de AC con unidades "de verdad".

Cada coche guarda su fisica en ``content/cars/<coche>/data/*.ini`` (o dentro de
``data.acd``, que de momento no se puede editar). Esta clase traduce esos .ini a
numeros con sentido (N/mm, N·s/mm, Nm, PSI, CV, km/h...) y sabe como escribir el
resultado de vuelta al .ini correspondiente.

Nada se escribe en disco hasta que se llama a :meth:`CarData.save`.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import units
from .ini_editor import ACIni
from .lut import LUT, RtoInfo, read_rto

__all__ = ["CarData", "TurboData", "PHYSICS_FILES", "DEFAULT_TURBO"]

# Ficheros que definen el comportamiento del coche en pista
PHYSICS_FILES = (
    "engine.ini",
    "drivetrain.ini",
    "suspensions.ini",
    "brakes.ini",
    "car.ini",
    "tyres.ini",
    "setup.ini",
    "electronics.ini",
    "power.lut",
    "coast.lut",
)

# Valores de partida para un turbo nuevo (los mismos que usa Kunos)
DEFAULT_TURBO: dict[str, float] = {
    "LAG_DN": 0.99,
    "LAG_UP": 0.997,
    "MAX_BOOST": 1.0,
    "WASTEGATE": 0.8,
    "DISPLAY_MAX_BOOST": 0.8,
    "REFERENCE_RPM": 2500,
    "GAMMA": 2.5,
    "COCKPIT_ADJUSTABLE": 0,
}

DEFAULT_WHEEL_RADIUS = 0.33  # metros: rueda de 17" con neumatico de perfil medio

# Ajustes escalares numéricos existentes que se pueden exponer en el editor avanzado.
# Se excluyen datos de identificación/flags y setup.ini, que define límites del juego.
ADVANCED_INI_FILES = (
    "engine.ini", "drivetrain.ini", "suspensions.ini", "brakes.ini",
    "car.ini", "tyres.ini", "electronics.ini",
)
ADVANCED_EXCLUDED_KEYS = {
    "VERSION", "INDEX", "PRESENT", "ACTIVE", "COCKPIT_ADJUSTABLE",
    "NAME", "TYPE", "SCREEN_NAME", "SHORT_NAME",
}
_NUMERIC_VALUE_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _safe_numeric_text(value) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    text = str(value).strip()
    if len(text) > 32 or "\\n" in text or "\\r" in text or "[" in text or "]" in text or "=" in text:
        return None
    try:
        parsed = float(text)
        return text if math.isfinite(parsed) and any(character.isdigit() for character in text) else None
    except ValueError:
        return None


@dataclass(frozen=True)
class AdvancedSetting:
    filename: str
    section: str
    key: str
    value: float

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.filename.upper(), self.section.upper(), self.key.upper())


@dataclass(frozen=True)
class DriftPresetResult:
    applied: tuple[str, ...]
    skipped: tuple[str, ...]
    reason: str = ""

    @property
    def changed_count(self) -> int:
        return len(self.applied)


@dataclass
class TurboData:
    """Un turbo del coche (seccion [TURBO_0], [TURBO_1]...)."""

    section: str
    index: int
    max_boost: float = 1.0
    wastegate: float = 0.0
    display_max_boost: float = 0.0
    reference_rpm: float = 2500.0
    lag_up: float = 0.997
    lag_dn: float = 0.99
    gamma: float = 2.5
    cockpit_adjustable: bool = False

    @property
    def boost_bar(self) -> float:
        """El turbo de AC no guarda bares: MAX_BOOST es un multiplicador de par."""
        return self.max_boost


def _is_gear_key(key: str) -> bool:
    suffix = key.upper().removeprefix("GEAR_")
    return key.upper().startswith("GEAR_") and suffix.isdigit() and 1 <= int(suffix) <= 12


def _is_turbo_section(section: str) -> bool:
    suffix = section.removeprefix("TURBO_")
    return section.startswith("TURBO_") and suffix.isdigit() and int(suffix) <= 15


class CarData:
    """Datos fisicos editables de un coche."""

    def __init__(
        self,
        data_dir: str | Path,
        name: str = "",
        ui_name: str = "",
        folder: str | Path | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.folder = Path(folder) if folder is not None else self.data_dir.parent
        self.name = name or self.data_dir.parent.name
        self.ui_name = ui_name or self.name
        self._ini: dict[str, ACIni] = {}
        self._lut: dict[str, LUT] = {}
        self._power_base: list[list[float]] | None = None
        self.power_scale: float = 1.0

    @classmethod
    def from_car(cls, car) -> CarData:  # car: ac_scanner.Car
        return cls(car.data_dir, name=car.name, ui_name=car.ui_name, folder=car.folder)

    # ------------------------------------------------------------------ base
    @property
    def editable(self) -> bool:
        return any((self.data_dir / name).is_file() for name in PHYSICS_FILES)

    def ini(self, filename: str) -> ACIni:
        ini = self._ini.get(filename)
        if ini is None:
            ini = ACIni(self.data_dir / filename)
            self._ini[filename] = ini
        return ini

    def lut(self, filename: str) -> LUT:
        lut = self._lut.get(filename)
        if lut is None:
            lut = LUT(self.data_dir / filename)
            self._lut[filename] = lut
        return lut

    def has_file(self, filename: str) -> bool:
        return (self.data_dir / filename).is_file()

    def missing_files(self) -> list[str]:
        return [name for name in PHYSICS_FILES if not self.has_file(name)]

    # accesos rapidos con valor por defecto
    def _get(self, filename: str, section: str, key: str, default: str = "") -> str:
        return self.ini(filename).get(section, key, default)

    def _float(self, filename: str, section: str, key: str, default: float = 0.0) -> float:
        return self.ini(filename).get_float(section, key, default)

    def _int(self, filename: str, section: str, key: str, default: int = 0) -> int:
        return self.ini(filename).get_int(section, key, default)

    def _set(self, filename: str, section: str, key: str, value) -> None:
        self.ini(filename).set_value(section, key, value)

    # --------------------------------------------------------------- motor
    @property
    def limiter(self) -> int:
        return self._int("engine.ini", "ENGINE_DATA", "LIMITER", 7000)

    @limiter.setter
    def limiter(self, value: int) -> None:
        self._set("engine.ini", "ENGINE_DATA", "LIMITER", int(value))

    @property
    def idle_rpm(self) -> int:
        return self._int("engine.ini", "ENGINE_DATA", "MINIMUM", 1000)

    @idle_rpm.setter
    def idle_rpm(self, value: int) -> None:
        self._set("engine.ini", "ENGINE_DATA", "MINIMUM", int(value))

    @property
    def engine_inertia(self) -> float:
        return self._float("engine.ini", "ENGINE_DATA", "INERTIA", 0.15)

    @engine_inertia.setter
    def engine_inertia(self, value: float) -> None:
        self._set("engine.ini", "ENGINE_DATA", "INERTIA", round(value, 4))

    @property
    def power_curve_file(self) -> str:
        return self._get("engine.ini", "HEADER", "POWER_CURVE", "power.lut").strip() or "power.lut"

    @property
    def power_lut(self) -> LUT | None:
        name = self.power_curve_file
        if not self.has_file(name):
            return None
        lut = self.lut(name)
        if self._power_base is None:
            self._power_base = [list(row) for row in lut.rows]
        return lut

    @property
    def damage(self) -> dict[str, float]:
        ini = self.ini("engine.ini")
        return {
            "rpm_threshold": ini.get_float("DAMAGE", "RPM_THRESHOLD", 0.0),
            "rpm_damage_k": ini.get_float("DAMAGE", "RPM_DAMAGE_K", 0.0),
            "turbo_threshold": ini.get_float("DAMAGE", "TURBO_BOOST_THRESHOLD", 0.0),
            "turbo_damage_k": ini.get_float("DAMAGE", "TURBO_DAMAGE_K", 0.0),
        }

    # ------------------------------------------------------------------ turbo
    @property
    def turbo_sections(self) -> list[str]:
        ini = self.ini("engine.ini")
        return [
            section
            for section in ini.sections()
            if section.upper().startswith("TURBO_") and ini.keys(section)
        ]

    @property
    def has_turbo(self) -> bool:
        return bool(self.turbo_sections)

    def turbos(self) -> list[TurboData]:
        out = []
        for index, section in enumerate(self.turbo_sections):
            ini = self.ini("engine.ini")
            out.append(
                TurboData(
                    section=section,
                    index=index,
                    max_boost=ini.get_float(section, "MAX_BOOST", 0.0),
                    wastegate=ini.get_float(section, "WASTEGATE", 0.0),
                    display_max_boost=ini.get_float(section, "DISPLAY_MAX_BOOST", 0.0),
                    reference_rpm=ini.get_float(section, "REFERENCE_RPM", 2500.0),
                    lag_up=ini.get_float(section, "LAG_UP", 0.997),
                    lag_dn=ini.get_float(section, "LAG_DN", 0.99),
                    gamma=ini.get_float(section, "GAMMA", 2.5),
                    cockpit_adjustable=ini.get_bool(section, "COCKPIT_ADJUSTABLE", False),
                )
            )
        return out

    def set_turbo(self, index: int = 0, **fields: float) -> None:
        sections = self.turbo_sections
        if not sections or not (0 <= index < len(sections)):
            return
        section = sections[index]
        for key, value in fields.items():
            if value is None:
                continue
            self._set("engine.ini", section, key.upper(), value)

    def add_turbo(self) -> str:
        """Anade un turbo (seccion [TURBO_0]) con valores de partida de Kunos.

        Si la seccion existia comentada (porque se quito antes), se reactiva.
        """
        section = "TURBO_0"
        for key, value in DEFAULT_TURBO.items():
            self._set("engine.ini", section, key, value)
        return section

    def remove_turbo(self, index: int = 0) -> None:
        """Comenta la seccion [TURBO_n]: el coche pasa a comportarse como atmosferico."""
        sections = self.turbo_sections
        if not sections or not (0 <= index < len(sections)):
            return
        self.ini("engine.ini").remove_section(sections[index])

    # --------------------------------------------------------- curva de potencia
    def power_points(self, scaled: bool = True) -> list[tuple[float, float]]:
        """Puntos (rpm, Nm) de la curva en memoria, o curva base con scaled=False."""
        lut = self.power_lut
        if lut is None:
            return []
        rows = lut.rows
        if not scaled and self._power_base is not None:
            rows = self._power_base
        return [(row[0], row[-1]) for row in rows if len(row) >= 2]

    def peak_torque(self, scaled: bool = True) -> tuple[float, float]:
        points = self.power_points(scaled)
        if not points:
            return (0.0, 0.0)
        return max(points, key=lambda point: point[1])

    def peak_power(self, scaled: bool = True) -> tuple[float, float]:
        """(rpm, CV) de potencia maxima."""
        points = self.power_points(scaled)
        if not points:
            return (0.0, 0.0)
        best = max(points, key=lambda point: units.hp_from_torque(point[1], point[0]))
        return (best[0], units.hp_from_torque(best[1], best[0]))

    def set_power_scale(self, factor: float) -> None:
        """Multiplica la curva de par entera (1.0 = sin tocar) sin acumular errores."""
        if self._power_base is None:
            self.power_lut  # fuerza la carga y guarda la curva original
        base = self._power_base
        lut = self.power_lut
        if base is None or lut is None:
            return
        self.power_scale = float(factor)
        lut.set_rows([[row[0], row[-1] * self.power_scale] for row in base])

    def reset_power_scale(self) -> None:
        self.set_power_scale(1.0)

    def set_power_point(self, index: int, torque_nm: float) -> bool:
        """Edita un punto existente de power.lut y mantiene coherente el escalado."""
        if not math.isfinite(float(torque_nm)):
            return False
        lut = self.power_lut
        if lut is None or not 0 <= index < lut.n_rows:
            return False
        lut.set(index, -1, float(torque_nm))
        if self._power_base is not None and self.power_scale:
            self._power_base[index][-1] = float(torque_nm) / self.power_scale
        return True

    @property
    def power_scale_applied(self) -> bool:
        lut = self._lut.get(self.power_curve_file)
        return bool(lut and lut.changed)

    # ------------------------------------------------------------- transmision
    @property
    def drive_type(self) -> str:
        return self._get("drivetrain.ini", "TRACTION", "TYPE", "RWD").strip().upper() or "RWD"

    @property
    def gear_count(self) -> int:
        count = self._int("drivetrain.ini", "GEARS", "COUNT", 0)
        if count > 0:
            return min(count, 12)
        return len(self.gear_ratios())

    def gear_ratios(self) -> list[float]:
        ini = self.ini("drivetrain.ini")
        count = max(self.gear_count, 1)
        ratios = []
        for index in range(1, count + 1):
            ratios.append(ini.get_float("GEARS", f"GEAR_{index}", 1.0))
        return ratios

    def set_gear(self, index: int, ratio: float) -> None:
        self._set("drivetrain.ini", "GEARS", f"GEAR_{index}", round(float(ratio), 4))

    def set_gear_count(self, count: int) -> None:
        """Cambia el numero de marchas y crea las claves que falten."""
        count = max(1, min(int(count), 12))
        ratios = self.gear_ratios()
        last = ratios[-1] if ratios else 1.0
        ini = self.ini("drivetrain.ini")
        for index in range(1, count + 1):
            if not ini.has("GEARS", f"GEAR_{index}"):
                self.set_gear(index, last)
        self._set("drivetrain.ini", "GEARS", "COUNT", count)

    @property
    def reverse_ratio(self) -> float:
        return self._float("drivetrain.ini", "GEARS", "GEAR_R", -3.5)

    @reverse_ratio.setter
    def reverse_ratio(self, value: float) -> None:
        self._set("drivetrain.ini", "GEARS", "GEAR_R", round(float(value), 4))

    @property
    def final_drive(self) -> float:
        return self._float("drivetrain.ini", "GEARS", "FINAL", 3.5)

    @final_drive.setter
    def final_drive(self, value: float) -> None:
        self._set("drivetrain.ini", "GEARS", "FINAL", round(float(value), 4))

    @property
    def differential(self) -> tuple[float, float, float]:
        ini = self.ini("drivetrain.ini")
        return (
            ini.get_float("DIFFERENTIAL", "POWER", 0.0),
            ini.get_float("DIFFERENTIAL", "COAST", 0.0),
            ini.get_float("DIFFERENTIAL", "PRELOAD", 0.0),
        )

    def set_differential(self, power: float, coast: float, preload: float) -> None:
        self._set("drivetrain.ini", "DIFFERENTIAL", "POWER", round(float(power), 4))
        self._set("drivetrain.ini", "DIFFERENTIAL", "COAST", round(float(coast), 4))
        self._set("drivetrain.ini", "DIFFERENTIAL", "PRELOAD", round(float(preload), 2))

    @property
    def clutch_max_torque(self) -> float:
        return self._float("drivetrain.ini", "CLUTCH", "MAX_TORQUE", 0.0)

    @property
    def ratios_rto(self) -> RtoInfo | None:
        return read_rto(self.data_dir / "ratios.rto")

    @property
    def final_rto(self) -> RtoInfo | None:
        return read_rto(self.data_dir / "final.rto")

    @property
    def has_gearset(self) -> bool:
        return self.has_file("ratios.rto")

    # --------------------------------------------------------------- neumaticos
    def wheel_radius(self, front: bool = True) -> float:
        section = "FRONT" if front else "REAR"
        radius = self._float("tyres.ini", section, "RADIUS", 0.0)
        if radius <= 0:
            radius = self._float("tyres.ini", section, "RIM_RADIUS", 0.0)
        return radius or DEFAULT_WHEEL_RADIUS

    def driven_wheel_radius(self) -> float:
        drive = self.drive_type
        if drive == "FWD":
            return self.wheel_radius(front=True)
        if drive == "RWD":
            return self.wheel_radius(front=False)
        return (self.wheel_radius(True) + self.wheel_radius(False)) / 2.0

    def compound_sections(self, front: bool = True) -> list[str]:
        prefix = "FRONT" if front else "REAR"
        out = []
        for section in self.ini("tyres.ini").sections():
            upper = section.upper()
            if upper == prefix or upper.startswith(prefix + "_"):
                out.append(section)
        return out

    def compounds(self) -> list[tuple[str, float]]:
        """[(nombre del compuesto, presion en PSI)] de los neumaticos delanteros."""
        ini = self.ini("tyres.ini")
        out = []
        for section in self.compound_sections(front=True):
            out.append(
                (
                    ini.get(section, "NAME", section),
                    ini.get_float(section, "PRESSURE_STATIC", 0.0),
                )
            )
        return out

    def tyre_pressure(self, front: bool = True) -> float:
        """Presion en frio (PSI) del primer compuesto de cada eje."""
        sections = self.compound_sections(front)
        return self._float("tyres.ini", sections[0], "PRESSURE_STATIC", 0.0) if sections else 0.0

    def set_tyre_pressure(self, front: bool, pressure_psi: float) -> None:
        """Ajusta la presion en frio del compuesto principal del eje."""
        sections = self.compound_sections(front)
        if sections:
            self._set("tyres.ini", sections[0], "PRESSURE_STATIC", round(float(pressure_psi), 2))

    # ----------------------------------------------------------- ayudas electronicas
    _AID_SECTIONS = {
        "ABS": ("ABS",),
        "TC": ("TRACTION", "TRACTION_CONTROL", "TCS"),
    }

    def driver_aids(self) -> dict[str, dict[str, str | bool]]:
        """Estado de ABS/TC si electronics.ini los declara de forma editable."""
        result: dict[str, dict[str, str | bool]] = {}
        if not self.has_file("electronics.ini"):
            return result
        ini = self.ini("electronics.ini")
        for aid, candidates in self._AID_SECTIONS.items():
            section = next((name for name in ini.sections() if name.upper() in candidates), None)
            if section is None:
                continue
            result[aid] = {
                "section": section,
                "available": ini.has(section, "PRESENT") and ini.has(section, "ACTIVE"),
                "present": ini.get_bool(section, "PRESENT", False),
                "active": ini.get_bool(section, "ACTIVE", False),
            }
        return result

    def set_driver_aid(
        self, aid: str, *, present: bool | None = None, active: bool | None = None
    ) -> bool:
        """Cambia solo banderas PRESENT/ACTIVE ya existentes; no inventa soporte del coche."""
        key = str(aid).upper()
        candidates = self._AID_SECTIONS.get(key)
        if not candidates or not self.has_file("electronics.ini"):
            return False
        ini = self.ini("electronics.ini")
        state = self.driver_aids().get(key)
        if not state or not state["available"]:
            return False
        section = str(state["section"])
        if present is not None:
            ini.set_value(section, "PRESENT", int(bool(present)))
        if active is not None:
            effective_present = bool(present) if present is not None else ini.get_bool(section, "PRESENT")
            ini.set_value(section, "ACTIVE", int(bool(active) and effective_present))
        elif present is False:
            ini.set_value(section, "ACTIVE", 0)
        return True

    def top_speed_kmh(self, gear_ratio: float, rpm: float | None = None) -> float:
                return units.speed_kmh(
            rpm if rpm is not None else float(self.limiter),
            gear_ratio,
            self.final_drive,
            self.driven_wheel_radius(),
        )

    def gear_top_speeds(self, rpm: float | None = None) -> list[float]:
        return [self.top_speed_kmh(ratio, rpm) for ratio in self.gear_ratios()]

    # --------------------------------------------------------------- suspension
    def spring_rate(self, front: bool = True) -> float:
        return self._float("suspensions.ini", "FRONT" if front else "REAR", "SPRING_RATE", 0.0)

    def set_spring_rate(self, front: bool, n_per_m: float) -> None:
        self._set(
            "suspensions.ini", "FRONT" if front else "REAR", "SPRING_RATE", round(float(n_per_m), 1)
        )

    def damper(self, front: bool, rebound: bool) -> float:
        key = "DAMP_REBOUND" if rebound else "DAMP_BUMP"
        return self._float("suspensions.ini", "FRONT" if front else "REAR", key, 0.0)

    def set_damper(self, front: bool, rebound: bool, n_sec_per_m: float) -> None:
        key = "DAMP_REBOUND" if rebound else "DAMP_BUMP"
        self._set(
            "suspensions.ini",
            "FRONT" if front else "REAR",
            key,
            round(float(n_sec_per_m), 1),
        )

    def bump_stop_rate(self, front: bool) -> float:
        return self._float("suspensions.ini", "FRONT" if front else "REAR", "BUMP_STOP_RATE", 0.0)

    def progressive_spring(self, front: bool) -> float:
        return self._float(
            "suspensions.ini", "FRONT" if front else "REAR", "PROGRESSIVE_SPRING_RATE", 0.0
        )

    def arb(self, front: bool) -> float:
        return self._float("suspensions.ini", "ARB", "FRONT" if front else "REAR", 0.0)

    def set_arb(self, front: bool, value: float) -> None:
        self._set("suspensions.ini", "ARB", "FRONT" if front else "REAR", round(float(value), 1))

    def ride_height_offset(self, front: bool) -> float:
        """ROD_LENGTH en metros: positivo sube el coche."""
        return self._float("suspensions.ini", "FRONT" if front else "REAR", "ROD_LENGTH", 0.0)

    def set_ride_height_offset(self, front: bool, metres: float) -> None:
        self._set(
            "suspensions.ini", "FRONT" if front else "REAR", "ROD_LENGTH", round(float(metres), 4)
        )

    @property
    def wheelbase(self) -> float:
        return self._float("suspensions.ini", "BASIC", "WHEELBASE", 0.0)

    @property
    def cg_front_percent(self) -> float:
        return self._float("suspensions.ini", "BASIC", "CG_LOCATION", 0.0) * 100.0

    # ------------------------------------------------------------------- frenos
    @property
    def brake_torque(self) -> float:
        return self._float("brakes.ini", "DATA", "MAX_TORQUE", 0.0)

    @brake_torque.setter
    def brake_torque(self, value: float) -> None:
        self._set("brakes.ini", "DATA", "MAX_TORQUE", round(float(value), 1))

    @property
    def brake_bias_percent(self) -> float:
        return self._float("brakes.ini", "DATA", "FRONT_SHARE", 0.5) * 100.0

    @brake_bias_percent.setter
    def brake_bias_percent(self, value: float) -> None:
        self._set("brakes.ini", "DATA", "FRONT_SHARE", round(float(value) / 100.0, 4))

    @property
    def handbrake_torque(self) -> float:
        return self._float("brakes.ini", "DATA", "HANDBRAKE_TORQUE", 0.0)

    # -------------------------------------------------------- peso y combustible
    @property
    def mass(self) -> float:
        return self._float("car.ini", "BASIC", "TOTALMASS", 0.0)

    @mass.setter
    def mass(self, value: float) -> None:
        self._set("car.ini", "BASIC", "TOTALMASS", round(float(value), 1))

    @property
    def fuel(self) -> float:
        return self._float("car.ini", "FUEL", "FUEL", 0.0)

    @property
    def max_fuel(self) -> float:
        return self._float("car.ini", "FUEL", "MAX_FUEL", 0.0)

    @max_fuel.setter
    def max_fuel(self, value: float) -> None:
        self._set("car.ini", "FUEL", "MAX_FUEL", round(float(value), 1))

    def power_weight(self, scaled: bool = True) -> tuple[float, float]:
        """(CV/tonelada, kg/CV)."""
        hp = self.peak_power(scaled)[1]
        return units.power_weight(self.mass, hp)

    # ------------------------------------------------------- editor avanzado
    def advanced_settings(self) -> list[AdvancedSetting]:
        """Ajustes físicos numéricos que ya existen en los INI abiertos del coche."""
        found: list[AdvancedSetting] = []
        for filename in ADVANCED_INI_FILES:
            if not self.has_file(filename):
                continue
            ini = self.ini(filename)
            for section in ini.sections():
                if section.upper() == "HEADER" or "GRAPHICS" in section.upper():
                    continue
                for key in ini.keys(section):
                    if key.upper() in ADVANCED_EXCLUDED_KEYS or "GRAPHICS" in key.upper():
                        continue
                    text = ini.get(section, key).strip()
                    if not _NUMERIC_VALUE_RE.fullmatch(text):
                        continue
                    try:
                        value = float(text)
                    except ValueError:
                        continue
                    if math.isfinite(value):
                        found.append(AdvancedSetting(filename, section, key, value))
        return found

    def set_advanced_value(self, filename: str, section: str, key: str, value: float | str) -> bool:
        """Cambia una clave numérica existente y elegible; nunca crea secciones/claves."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(number):
            return False
        match = next(
            (entry for entry in self.advanced_settings() if entry.identity ==
             (filename.upper(), section.upper(), key.upper())),
            None,
        )
        if match is None:
            return False
        self.ini(match.filename).set_value(match.section, match.key, number)
        return True

    def _restore_advanced_value(self, filename: str, section: str, key: str, value: str) -> None:
        """Restaura el valor numérico original conservando su formato textual."""
        entry = next((item for item in self.advanced_settings() if item.identity ==
                      (filename.upper(), section.upper(), key.upper())), None)
        if entry is not None:
            self.ini(entry.filename).set_value(entry.section, entry.key, value)

    def apply_drift_preset(self) -> DriftPresetResult:
        """Prepara un ajuste de drift conservador sobre claves existentes del coche.

        Solo modifica datos en memoria; el usuario conserva el control del guardado.
        """
        if self.drive_type not in {"RWD", "4WD", "AWD"}:
            return DriftPresetResult((), (), "El preset de drift requiere un coche RWD o AWD; este coche es FWD.")
        available = {entry.identity: entry.value for entry in self.advanced_settings()}
        proposed: list[tuple[str, str, str, float, str]] = []

        def add(filename: str, section: str, key: str, value: float, label: str) -> None:
            identity = (filename.upper(), section.upper(), key.upper())
            if identity in available and math.isfinite(value):
                proposed.append((filename, section, key, value, label))

        final = available.get(("DRIVETRAIN.INI", "GEARS", "FINAL"))
        if final is not None and 0.5 <= final <= 10:
            target = final * 1.05
            limits = self.setup_range("FINAL", "FINAL_DRIVE")
            if limits:
                target = min(max(target, limits[0]), limits[1])
            add("drivetrain.ini", "GEARS", "FINAL", target, "grupo final +5%")

        power = available.get(("DRIVETRAIN.INI", "DIFFERENTIAL", "POWER"))
        coast = available.get(("DRIVETRAIN.INI", "DIFFERENTIAL", "COAST"))
        diff_scale = 100.0 if max(power or 0, coast or 0) > 1.01 else 1.0
        if power is not None and 0 <= power <= 100 * diff_scale:
            add("drivetrain.ini", "DIFFERENTIAL", "POWER", max(power, 0.70 * diff_scale), "bloqueo aceleración")
        if coast is not None and 0 <= coast <= 100 * diff_scale:
            add("drivetrain.ini", "DIFFERENTIAL", "COAST", min(coast, 0.25 * diff_scale), "bloqueo retención")
        preload = available.get(("DRIVETRAIN.INI", "DIFFERENTIAL", "PRELOAD"))
        if preload is not None and 0 <= preload <= 500:
            add("drivetrain.ini", "DIFFERENTIAL", "PRELOAD", max(preload, 25.0), "precarga diferencial")

        bias = available.get(("BRAKES.INI", "DATA", "FRONT_SHARE"))
        if bias is not None and 0 <= bias <= 100:
            scale = 100.0 if bias > 1.01 else 1.0
            add("brakes.ini", "DATA", "FRONT_SHARE", 0.67 * scale, "reparto de freno 67% delante")

        rear_pressure = next((
            entry for entry in self.advanced_settings()
            if entry.filename == "tyres.ini" and entry.section.upper() == "REAR"
            and entry.key.upper() == "PRESSURE_STATIC"
        ), None)
        if rear_pressure is not None and 5 <= rear_pressure.value <= 60:
            target = rear_pressure.value + 1.0
            limits = self.setup_range("PRESSURE_RR", "PRESSURE_LR", "PRESSURE_REAR")
            if limits:
                target = min(max(target, limits[0]), limits[1])
            add("tyres.ini", rear_pressure.section, rear_pressure.key, target, "presión trasera +1 PSI")

        handbrake = available.get(("BRAKES.INI", "DATA", "HANDBRAKE_TORQUE"))
        if handbrake is not None and 0 < handbrake <= 5000:
            add("brakes.ini", "DATA", "HANDBRAKE_TORQUE", min(handbrake * 1.25, 5000), "freno de mano +25%")

        applied = []
        for filename, section, key, value, label in proposed:
            if abs(value - available[(filename.upper(), section.upper(), key.upper())]) < 1e-9:
                continue
            if self.set_advanced_value(filename, section, key, value):
                applied.append(label)
        skipped = tuple(label for *_fields, label in proposed if label not in applied)
        if not applied:
            reason = "Este coche no declara parámetros compatibles con el preset; no se ha cambiado nada."
        else:
            reason = "Ajuste orientativo, adaptado a los campos presentes. Revisa el resultado en pista."
        if self.drive_type in {"4WD", "AWD"} and applied:
            reason += " Es tracción total; el preset no puede separar un diferencial central que no esté expuesto."
        return DriftPresetResult(tuple(applied), skipped, reason)

    # --------------------------------------------------- rangos oficiales del setup
    def setup_range(self, *candidates: str) -> tuple[float, float, float] | None:
        """Rango (min, max, paso) que el propio coche declara en setup.ini.

        Las secciones de setup.ini se llaman SPRING_RATE_FRONT, ARB_REAR,
        PRESSURE_LF... Se prueban los nombres candidatos y se devuelve el primero
        que tenga MIN y MAX. Se usa para que los controles no salgan de lo que AC
        acepta en el setup del coche.
        """
        ini = self.ini("setup.ini")
        wanted = {name.upper() for name in candidates}
        for section in ini.sections():
            if section.upper() not in wanted:
                continue
            if not ini.has(section, "MIN") or not ini.has(section, "MAX"):
                continue
            return (
                ini.get_float(section, "MIN", 0.0),
                ini.get_float(section, "MAX", 1.0),
                ini.get_float(section, "STEP", 1.0) or 1.0,
            )
        return None

    # ------------------------------------------------------------- presets de setup
    def setup_snapshot(self) -> dict:
        """Captura ajustes seleccionados para perfiles y deshacer/rehacer."""
        sections_by_file = {
            "engine.ini": {
                "ENGINE_DATA": ("LIMITER", "MINIMUM", "INERTIA"),
                "TURBO_0": (
                    "MAX_BOOST", "WASTEGATE", "DISPLAY_MAX_BOOST", "REFERENCE_RPM",
                    "LAG_UP", "LAG_DN", "GAMMA", "COCKPIT_ADJUSTABLE",
                ),
            },
            "drivetrain.ini": {
                "GEARS": ("COUNT", "GEAR_R", "FINAL"),
                "DIFFERENTIAL": ("POWER", "COAST", "PRELOAD"),
            },
            "suspensions.ini": {
                "FRONT": (
                    "SPRING_RATE", "DAMP_BUMP", "DAMP_REBOUND", "BUMP_STOP_RATE",
                    "ROD_LENGTH", "STATIC_CAMBER",
                ),
                "REAR": (
                    "SPRING_RATE", "DAMP_BUMP", "DAMP_REBOUND", "BUMP_STOP_RATE",
                    "ROD_LENGTH", "STATIC_CAMBER",
                ),
                "ARB": ("FRONT", "REAR"),
            },
            "brakes.ini": {"DATA": ("MAX_TORQUE", "FRONT_SHARE")},
            "car.ini": {"BASIC": ("TOTALMASS",), "FUEL": ("MAX_FUEL",)},
            "tyres.ini": {"FRONT": ("PRESSURE_STATIC",), "REAR": ("PRESSURE_STATIC",)},
            "electronics.ini": {
                section: ("PRESENT", "ACTIVE")
                for section in ("ABS", "TRACTION", "TRACTION_CONTROL", "TCS")
            },
        }
        values: dict[str, dict[str, dict[str, str]]] = {}
        for filename, sections in sections_by_file.items():
            if not self.has_file(filename):
                continue
            ini = self.ini(filename)
            captured: dict[str, dict[str, str]] = {}
            for section, keys in sections.items():
                for key in keys:
                    if ini.has(section, key):
                        captured.setdefault(section, {})[key] = ini.get(section, key)
            if captured:
                values[filename] = captured

        if self.has_file("drivetrain.ini"):
            drivetrain = self.ini("drivetrain.ini")
            gears = {
                f"GEAR_{index}": drivetrain.get("GEARS", f"GEAR_{index}")
                for index in range(1, self.gear_count + 1)
                if drivetrain.has("GEARS", f"GEAR_{index}")
            }
            if gears:
                values.setdefault("drivetrain.ini", {}).setdefault("GEARS", {}).update(gears)

        turbos = []
        if self.has_file("engine.ini"):
            engine = self.ini("engine.ini")
            turbo_keys = sections_by_file["engine.ini"]["TURBO_0"]
            for section in self.turbo_sections:
                captured = {key: engine.get(section, key) for key in turbo_keys if engine.has(section, key)}
                if captured:
                    turbos.append({"section": section, "values": captured})
        power = self.power_lut
        advanced: dict[str, dict[str, dict[str, str]]] = {}
        for entry in self.advanced_settings():
            advanced.setdefault(entry.filename, {}).setdefault(entry.section, {})[entry.key] = self.ini(entry.filename).get(entry.section, entry.key)
        return {
            "version": 1,
            "values": values,
            "advanced": advanced,
            "turbos": turbos,
            "power_curve": [list(row) for row in power.rows] if power is not None else [],
        }

    def restore_setup(self, snapshot: dict) -> None:
        """Restaura una captura validada en memoria; nunca ejecuta ni escribe en disco."""
        if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
            raise ValueError("Formato de setup no compatible")
        values = snapshot.get("values", {})
        if not isinstance(values, dict) or len(values) > len(PHYSICS_FILES):
            raise ValueError("El setup no contiene valores válidos")

        supported = {
            "engine.ini": {
                "ENGINE_DATA": {"LIMITER", "MINIMUM", "INERTIA"},
                "TURBO": {"MAX_BOOST", "WASTEGATE", "DISPLAY_MAX_BOOST", "REFERENCE_RPM", "LAG_UP", "LAG_DN", "GAMMA", "COCKPIT_ADJUSTABLE"},
            },
            "drivetrain.ini": {
                "GEARS": {"COUNT", "GEAR_R", "FINAL"},
                "DIFFERENTIAL": {"POWER", "COAST", "PRELOAD"},
            },
            "suspensions.ini": {
                "FRONT": {"SPRING_RATE", "DAMP_BUMP", "DAMP_REBOUND", "BUMP_STOP_RATE", "ROD_LENGTH", "STATIC_CAMBER"},
                "REAR": {"SPRING_RATE", "DAMP_BUMP", "DAMP_REBOUND", "BUMP_STOP_RATE", "ROD_LENGTH", "STATIC_CAMBER"},
                "ARB": {"FRONT", "REAR"},
            },
            "brakes.ini": {"DATA": {"MAX_TORQUE", "FRONT_SHARE"}},
            "car.ini": {"BASIC": {"TOTALMASS"}, "FUEL": {"MAX_FUEL"}},
            "tyres.ini": {"FRONT": {"PRESSURE_STATIC"}, "REAR": {"PRESSURE_STATIC"}},
            "electronics.ini": {
                "ABS": {"PRESENT", "ACTIVE"},
                "TRACTION": {"PRESENT", "ACTIVE"},
                "TRACTION_CONTROL": {"PRESENT", "ACTIVE"},
                "TCS": {"PRESENT", "ACTIVE"},
            },
        }

        if "drivetrain.ini" in values:
            drivetrain_values = values["drivetrain.ini"]
            if not isinstance(drivetrain_values, dict) or not isinstance(drivetrain_values.get("GEARS", {}), dict):
                raise ValueError("El perfil contiene marchas no válidas")
        turbo_data = snapshot.get("turbos", [])
        if not isinstance(turbo_data, list) or len(turbo_data) > 16:
            raise ValueError("El perfil contiene turbos no válidos")
        for entry in turbo_data:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("values"), dict)
                or not _is_turbo_section(str(entry.get("section", "")).upper())
            ):
                raise ValueError("El perfil contiene turbos no válidos")
        advanced_data = snapshot.get("advanced", {})
        if not isinstance(advanced_data, dict) or len(advanced_data) > len(ADVANCED_INI_FILES):
            raise ValueError("El perfil contiene parámetros avanzados no válidos")
        for filename, sections in advanced_data.items():
            if filename not in ADVANCED_INI_FILES or not isinstance(sections, dict) or len(sections) > 128:
                raise ValueError("El perfil contiene parámetros avanzados no válidos")
            for section, keys in sections.items():
                if not isinstance(section, str) or len(section) > 80 or not isinstance(keys, dict) or len(keys) > 256:
                    raise ValueError("El perfil contiene parámetros avanzados no válidos")
                for key, value in keys.items():
                    if not isinstance(key, str) or len(key) > 80 or _safe_numeric_text(value) is None:
                        raise ValueError("El perfil contiene parámetros avanzados no válidos")

        power_rows = snapshot.get("power_curve", [])
        if not isinstance(power_rows, list) or len(power_rows) > 10000:
            raise ValueError("El perfil contiene una curva no válida")
        if power_rows:
            target_lut = self.power_lut
            if target_lut is None or len(power_rows) != target_lut.n_rows:
                raise ValueError("El perfil contiene un numero de puntos distinto al del coche")
            if any(not isinstance(row, list) or len(row) != target_lut.n_cols for row in power_rows):
                raise ValueError("La curva del perfil no coincide con la de este coche")
            try:
                power_rows = [[float(value) for value in row] for row in power_rows]
            except (TypeError, ValueError):
                raise ValueError("El perfil contiene una curva no válida") from None
            if any(not math.isfinite(value) for row in power_rows for value in row):
                raise ValueError("El perfil contiene una curva no válida")

        if self.has_file("drivetrain.ini"):
            current = self.ini("drivetrain.ini")
            drivetrain_values = values.get("drivetrain.ini", {})
            target_gears = drivetrain_values.get("GEARS", {}) if isinstance(drivetrain_values, dict) else {}
            if not isinstance(target_gears, dict):
                raise ValueError("El perfil contiene marchas no válidas")
            target_gear_names = {
                str(key).upper() for key in target_gears
                if _is_gear_key(str(key))
            } if isinstance(target_gears, dict) else set()
            for key in current.keys("GEARS"):
                if _is_gear_key(key) and key.upper() not in target_gear_names:
                    current.remove_key("GEARS", key)

        for filename, sections in values.items():
            if filename not in supported or not isinstance(sections, dict) or not self.has_file(filename):
                continue
            ini = self.ini(filename)
            for section, keys in sections.items():
                if not isinstance(keys, dict):
                    continue
                section_upper = str(section).upper()
                allowed = None
                if filename == "engine.ini" and _is_turbo_section(section_upper):
                    allowed = supported[filename]["TURBO"]
                else:
                    allowed = supported[filename].get(section_upper)
                if allowed is None:
                    continue
                for key, value in keys.items():
                    key_upper = str(key).upper()
                    gear_key = filename == "drivetrain.ini" and section_upper == "GEARS" and _is_gear_key(key_upper)
                    if key_upper not in allowed and not gear_key:
                        continue
                    safe_value = _safe_numeric_text(value)
                    if safe_value is not None and ini.has(section, key):
                        ini.set_value(section, key, safe_value)

        if self.has_file("engine.ini"):
            engine = self.ini("engine.ini")
            wanted: dict[str, tuple[str, dict[str, str]]] = {}
            turbo_fields = supported["engine.ini"]["TURBO"]
            for entry in turbo_data:
                if not isinstance(entry, dict) or not isinstance(entry.get("values"), dict):
                    continue
                section = str(entry.get("section", "")).upper()
                if not _is_turbo_section(section):
                    continue
                safe_values = {
                    str(key): safe for key, value in entry["values"].items()
                    if str(key).upper() in turbo_fields
                    and (safe := _safe_numeric_text(value)) is not None
                }
                if safe_values:
                    wanted[section] = (str(entry.get("section")), safe_values)
            for section in list(self.turbo_sections):
                if section.upper() not in wanted:
                    engine.remove_section(section)
            for section, safe_values in wanted.values():
                if not engine.has_section(section):
                    if section.upper() != "TURBO_0":
                        raise ValueError("No se pueden crear turbos distintos de TURBO_0")
                    self.add_turbo()
                for key, value in safe_values.items():
                    engine.set_value(section, key, value)

        advanced = snapshot.get("advanced", {})
        if isinstance(advanced, dict) and len(advanced) <= len(ADVANCED_INI_FILES):
            for filename, sections in advanced.items():
                if filename not in ADVANCED_INI_FILES or not isinstance(sections, dict):
                    continue
                for section, keys in sections.items():
                    if not isinstance(keys, dict):
                        continue
                    for key, value in keys.items():
                        if not isinstance(key, str) or len(key) > 80:
                            continue
                        safe = _safe_numeric_text(value)
                        if safe is not None:
                            self._restore_advanced_value(filename, str(section), key, safe)

        if power_rows and self.power_lut is not None:
            old_base = [list(row) for row in (self._power_base or self.power_lut.rows)]
            self.power_lut.set_rows(power_rows)
            ratios = [
                current[-1] / original[-1]
                for original, current in zip(old_base, power_rows)
                if len(original) == len(current) and original[-1] != 0
            ]
            if ratios and max(ratios) - min(ratios) <= 1e-6:
                self.power_scale = sum(ratios) / len(ratios)
                self._power_base = [
                    [*row[:-1], row[-1] / self.power_scale] if self.power_scale else list(row)
                    for row in power_rows
                ]
            else:
                self.power_scale = 1.0
                self._power_base = [list(row) for row in power_rows]

    def _restore_advanced_value(self, filename: str, section: str, key: str, value: str) -> None:
        """Restaura el texto original de un parámetro avanzado existente sin normalizarlo."""
        entry = next((item for item in self.advanced_settings() if item.identity ==
                      (filename.upper(), section.upper(), key.upper())), None)
        if entry is not None:
            self.ini(filename).set_value(entry.section, entry.key, value)

    # ------------------------------------------------------------- guardar / estado
    def dirty_files(self) -> list[str]:
        names = [name for name, ini in self._ini.items() if ini.changed]
        names += [name for name, lut in self._lut.items() if lut.changed]
        return sorted(set(names))

    @property
    def changed(self) -> bool:
        return bool(self.dirty_files())

    def save(self) -> list[str]:
        """Guarda ficheros tocados tras una instantánea del data original."""
        dirty = self.dirty_files()
        if not dirty:
            return []
        # Import local para evitar el ciclo swaps -> CarData. Si el respaldo falla,
        # se aborta el guardado: no se modifica ningún archivo sin copia previa.
        from .swaps import create_backup

        create_backup(self.folder)
        saved = []
        for name in dirty:
            obj = self._ini.get(name) or self._lut.get(name)
            if obj is not None and obj.save():
                saved.append(name)
                if name == self.power_curve_file and name in self._lut:
                    self._power_base = [list(row) for row in self._lut[name].rows]
                    self.power_scale = 1.0
        return saved

    def reload(self) -> None:
        self._ini.clear()
        self._lut.clear()
        self._power_base = None
        self.power_scale = 1.0

    # ------------------------------------------------------------- diagnostico
    def alerts(self) -> list[tuple[str, str]]:
        """[(nivel, mensaje)] con el nivel en 'peligro' | 'aviso' | 'info'."""
        out: list[tuple[str, str]] = []
        ini = self.ini("engine.ini")
        damage = self.damage

        for turbo in self.turbos():
            threshold = damage["turbo_threshold"]
            if threshold and turbo.max_boost > threshold:
                out.append(
                    (
                        "peligro",
                        f"MAX_BOOST {turbo.max_boost:.2f} de {turbo.section} pasa el umbral de "
                        f"dano del motor ({threshold:.2f}): AC aplicara dano al turbo.",
                    )
                )
            if turbo.max_boost < turbo.wastegate:
                out.append(
                    (
                        "aviso",
                        f"{turbo.section}: la wastegate ({turbo.wastegate:.2f}) esta por encima "
                        "del boost maximo, asi que no llegara a actuar.",
                    )
                )

        rpm_threshold = damage["rpm_threshold"]
        if rpm_threshold and self.limiter and self.limiter > rpm_threshold:
            out.append(
                (
                    "aviso",
                    f"El limitador ({self.limiter} rpm) esta por encima del umbral de dano del "
                    f"motor ({rpm_threshold:.0f} rpm).",
                )
            )
        if self.limiter == 0:
            out.append(("aviso", "LIMITER=0 significa que el motor no tiene corte de revoluciones."))

        if not self.has_file(self.power_curve_file):
            out.append(
                ("aviso", f"Falta la curva de potencia ({self.power_curve_file}): sin ella el motor no tira.")
            )

        if self.drive_type == "FWD" and self.differential[2] > 60:
            out.append(("info", "Traccion delantera con preload alto: el coche subvirara al frenar."))

        if self.has_gearset:
            rto = self.ratios_rto
            if rto is not None:
                out.append(
                    (
                        "info",
                        f"Este coche trae un gearset con {rto.count} relaciones en ratios.rto. "
                        "El setup del coche elige entre ellas; lo que se edita aqui es la relacion "
                        "de serie (drivetrain.ini).",
                    )
                )

        missing = [name for name in ("engine.ini", "drivetrain.ini", "suspensions.ini", "tyres.ini") if not self.has_file(name)]
        if missing:
            out.append(("aviso", "Faltan ficheros de fisica: " + ", ".join(missing)))

        if not out:
            out.append(("info", "Sin avisos: los valores estan dentro de lo razonable."))
        return out

    def summary(self, scaled: bool = True) -> list[tuple[str, str]]:
        """[(etiqueta, valor)] con la ficha del coche, para el panel de resumen."""
        torque_rpm, torque = self.peak_torque(scaled)
        hp_rpm, hp = self.peak_power(scaled)
        cv_per_tonne, kg_per_cv = self.power_weight(scaled)
        top = max(self.gear_top_speeds(), default=0.0)
        rows = [
            ("Coche", self.ui_name),
            ("Carpeta", self.name),
            ("Traccion", self.drive_type),
            ("Peso", f"{self.mass:.0f} kg"),
            ("Curva de par", f"{self.power_lut.n_rows if self.power_lut else 0} puntos"),
            ("Par maximo", f"{torque:.0f} Nm a {torque_rpm:.0f} rpm"),
            ("Potencia maxima", f"{hp:.0f} CV a {hp_rpm:.0f} rpm"),
            ("Relacion peso/potencia", f"{cv_per_tonne:.0f} CV/t  ·  {kg_per_cv:.2f} kg/CV"),
            ("Limitador", f"{self.limiter} rpm"),
            ("Marchas", f"{self.gear_count} ({self.drive_type})"),
            ("Grupo final", f"{self.final_drive:.3f}"),
            ("Velocidad teorica max.", f"{top:.0f} km/h"),
            ("Muelles del./tras.", f"{units.spring_to_nmm(self.spring_rate(True)):.0f} / "
                                    f"{units.spring_to_nmm(self.spring_rate(False)):.0f} N/mm"),
            ("Rueda motriz", f"{self.driven_wheel_radius() * 1000:.0f} mm de radio"),
        ]
        turbos = self.turbos()
        if turbos:
            rows.append(("Turbo", f"{len(turbos)} · MAX_BOOST {turbos[0].max_boost:.2f}"))
        else:
            rows.append(("Turbo", "no"))
        return rows
