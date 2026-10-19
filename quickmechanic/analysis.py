"""Calculos del taller: rendimiento estimado, gearing, comparacion y diagnostico.

Todo lo de este modulo es aritmetica determinista sobre lo que Quick Mechanic ya
ha leido del coche (curva de par, relaciones, peso, aero aproximada). No toca
disco ni necesita Assetto Corsa abierto, asi que se puede probar en los tests.

Las estimaciones se apoyan en un modelo cuasi-estatico de resistencia y traccion:
cuando un dato no existe en el coche se usa un valor tipico declarado aqui, y el
resultado se marca con ``assumptions`` para que la interfaz pueda explicarlo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import units
from .i18n import tr

__all__ = [
    "Finding",
    "GearSpeed",
    "GearingPlan",
    "PerformanceEstimate",
    "StyleResult",
    "CIRCUIT_PROFILES",
    "STYLE_LABELS",
    "apply_gearing",
    "apply_style",
    "aero_cda",
    "compare_cars",
    "shift_rpm",
    "diagnostics",
    "estimate_performance",
    "gear_speeds",
    "library_stats",
    "optimal_gearing",
    "report",
    "severity_counts",
]

RHO = 1.225                 # densidad del aire (kg/m3)
GRAVITY = 9.81
DEFAULT_CDA = 0.90          # Cd * A tipico de un GT (m2)
DEFAULT_ROLLING = 0.013     # coeficiente de rodadura
DRIVETRAIN_EFFICIENCY = 0.90
DEFAULT_TYRE_MU = 1.35
ROTATING_MASS_FACTOR = 1.06
DEFAULT_MASS = 1200.0
MAX_SIM_TIME = 90.0
SPEED_STEP_KMH = 0.5

# Nivel de aviso -> icono del diagnostico visual.
LEVEL_ICONS = {"ok": "🟢", "warn": "🟡", "error": "🔴"}


@dataclass(frozen=True)
class Finding:
    """Un aviso del validador, con su area y su nivel."""

    level: str
    area: str
    message: str

    @property
    def icon(self) -> str:
        return LEVEL_ICONS.get(self.level, "🟡")


@dataclass(frozen=True)
class GearSpeed:
    """Velocidad teorica de una marcha."""

    gear: int
    ratio: float
    shift_kmh: float
    power_kmh: float


@dataclass(frozen=True)
class PerformanceEstimate:
    """Estimacion de prestaciones a partir de los .ini actuales."""

    mass_kg: float
    power_hp: float
    power_rpm: float
    torque_nm: float
    torque_rpm: float
    cv_per_tonne: float
    kg_per_cv: float
    zero_100: float | None
    zero_200: float | None
    top_speed_kmh: float
    max_accel_g: float
    traction_limited: bool
    cda: float
    mu: float
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class GearingPlan:
    """Propuesta de relaciones de cambio."""

    ratios: tuple[float, ...]
    final_drive: float
    top_speed_kmh: float
    first_gear_force_n: float
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StyleResult:
    """Resultado de aplicar un preset de estilo (Street, Track, Drift...)."""

    applied: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def changed_count(self) -> int:
        return len(self.applied)


# ------------------------------------------------------------------ fundamentos
def _mass(car) -> float:
    mass = float(car.mass or 0.0)
    return mass if math.isfinite(mass) and mass >= 200.0 else DEFAULT_MASS


def _points(car) -> list[tuple[float, float]]:
    points = [(float(rpm), float(nm)) for rpm, nm in car.power_points() if nm > 0]
    points.sort(key=lambda point: point[0])
    return points


def _shift_rpm(car) -> float:
    limiter = float(car.limiter or 0)
    if limiter <= 0:
        rpm, _hp = car.peak_power()
        limiter = max(rpm * 1.05, 7000.0)
    return limiter * 0.97


def _driven_share(car) -> float:
    """Fraccion del peso que carga el eje motriz (limite de traccion)."""
    cg_front = car.cg_front_percent / 100.0
    if not 0.05 <= cg_front <= 0.95:
        cg_front = 0.5
    drive = car.drive_type
    if drive in {"AWD", "AWD2", "4WD"}:
        return 0.95
    if drive == "FWD":
        return cg_front
    return 1.0 - cg_front


def aero_cda(car) -> float:
    """Cd*A estimado: la aero real de AC vive en aero.ini y no siempre existe."""
    wings = [
        entry for entry in car.advanced_settings()
        if entry.filename.lower() == "aero.ini"
    ]
    cd_gain = sum(
        entry.value for entry in wings
        if entry.key.upper() in {"CD_GAIN", "CD"} and 0 < entry.value < 5
    )
    return DEFAULT_CDA + min(cd_gain, 0.8)


def shift_rpm(car) -> float:
    """Regimen de cambio: el limitador menos un 3 % de margen."""
    return _shift_rpm(car)


def _wheel_force(car, rpm: float, gear_ratio: float, torque: float | None = None) -> float:
    """Fuerza en rueda (N) para un regimen y una relacion de cambio."""
    if torque is None:
        torque = units.torque_at_rpm(_points(car), rpm)
    radius = car.driven_wheel_radius() or 0.33
    return torque * gear_ratio * car.final_drive * DRIVETRAIN_EFFICIENCY / radius


def _losses(car, speed_kmh: float, cda: float) -> float:
    v = max(speed_kmh, 0.0) / 3.6
    drag = 0.5 * RHO * cda * v * v
    rolling = DEFAULT_ROLLING * _mass(car) * GRAVITY
    return drag + rolling


def _best_gear(car, speed_kmh: float, ratios: list[float], shift_rpm: float, idle: float):
    """Marcha con mas fuerza disponible sin pasarse de revoluciones."""
    best = None
    for index, ratio in enumerate(ratios, start=1):
        rpm = units.rpm_at_speed(speed_kmh, ratio, car.final_drive, car.driven_wheel_radius() or 0.33)
        if rpm > shift_rpm or rpm < idle:
            continue
        force = _wheel_force(car, rpm, ratio)
        if best is None or force > best[1]:
            best = (index, force, ratio, rpm)
    return best


# ----------------------------------------------------------------- prestaciones
def estimate_performance(car) -> PerformanceEstimate | None:
    """Estima 0-100, 0-200, velocidad punta y aceleracion lateral disponible."""
    points = _points(car)
    if len(points) < 2:
        return None
    ratios = [ratio for ratio in car.gear_ratios() if ratio > 0]
    if not ratios or car.final_drive <= 0:
        return None
    mass = _mass(car)
    shift_rpm = _shift_rpm(car)
    idle = float(car.idle_rpm or 900)
    radius = car.driven_wheel_radius() or 0.33
    cda = aero_cda(car)
    mu = DEFAULT_TYRE_MU
    traction = mu * mass * GRAVITY * _driven_share(car)
    effective_mass = mass * ROTATING_MASS_FACTOR

    torque_rpm, torque = car.peak_torque()
    power_rpm, power_hp = car.peak_power()

    times: dict[float, float] = {}
    elapsed = 0.0
    top = 0.0
    max_accel = 0.0
    traction_limited = False
    # La simulacion arranca con el embrague patinando hasta el ralenti en primera:
    # por debajo de eso el motor no esta en su regimen util.
    speed = min(units.speed_kmh(idle, ratios[0], car.final_drive, radius), 20.0)
    while speed < 700.0 and elapsed < MAX_SIM_TIME:
        chosen = _best_gear(car, speed, ratios, shift_rpm, idle)
        if chosen is None:
            if speed > 30.0:
                break
            # Arranque: por debajo del ralenti en primera el coche sale patinando
            # el embrague, asi que se usa la fuerza de primera a ralenti.
            chosen = (1, _wheel_force(car, max(idle, 1.0), ratios[0]), ratios[0], idle)
        _index, force, _ratio, _rpm = chosen
        if force >= traction:
            traction_limited = True
            force = traction
        net = force - _losses(car, speed, cda)
        accel = net / effective_mass
        if accel <= 0.01:
            break
        max_accel = max(max_accel, accel)
        step = SPEED_STEP_KMH / 3.6
        elapsed += step / accel
        speed += SPEED_STEP_KMH
        top = speed
        for target in (100.0, 200.0):
            if target not in times and speed >= target:
                times[target] = elapsed
    if top <= 0:
        return None
    cv_per_tonne, kg_per_cv = car.power_weight()
    assumptions = [
        tr("Cd·A estimada: {0} m²", f"{cda:.2f}"),
        tr("Coeficiente de agarre asumido: {0}", f"{mu:.2f}"),
        tr("Rendimiento de transmision: {0} %", f"{DRIVETRAIN_EFFICIENCY * 100:.0f}"),
        tr("Salida con embrague: el cronometro arranca al ralenti en primera."),
    ]
    return PerformanceEstimate(
        mass_kg=mass,
        power_hp=power_hp,
        power_rpm=power_rpm,
        torque_nm=torque,
        torque_rpm=torque_rpm,
        cv_per_tonne=cv_per_tonne,
        kg_per_cv=kg_per_cv,
        zero_100=times.get(100.0),
        zero_200=times.get(200.0),
        top_speed_kmh=top,
        max_accel_g=max_accel / GRAVITY,
        traction_limited=traction_limited,
        cda=cda,
        mu=mu,
        assumptions=tuple(assumptions),
    )


# --------------------------------------------------------------------- gearing
def gear_speeds(car, rpm: float | None = None) -> list[GearSpeed]:
    """Velocidad de cada marcha al limitador y a la rpm de potencia maxima."""
    ratios = [ratio for ratio in car.gear_ratios() if ratio > 0]
    if not ratios or car.final_drive <= 0:
        return []
    shift_rpm = float(rpm or _shift_rpm(car))
    power_rpm = car.peak_power()[0] or shift_rpm
    radius = car.driven_wheel_radius() or 0.33
    out = []
    for index, ratio in enumerate(ratios, start=1):
        out.append(
            GearSpeed(
                gear=index,
                ratio=ratio,
                shift_kmh=units.speed_kmh(shift_rpm, ratio, car.final_drive, radius),
                power_kmh=units.speed_kmh(min(power_rpm, shift_rpm), ratio, car.final_drive, radius),
            )
        )
    return out


CIRCUIT_PROFILES: dict[str, float] = {
    "Monza": 340.0,
    "Spa-Francorchamps": 315.0,
    "Nürburgring Nordschleife": 300.0,
    "Mugello": 295.0,
    "Silverstone": 300.0,
    "Imola": 290.0,
    "Barcelona": 300.0,
    "Brands Hatch": 245.0,
    "Zandvoort": 265.0,
    "Drift (tandem)": 180.0,
    "Drag 1/4 milla": 250.0,
    "Autopista": 380.0,
}


def _top_speed_from_power(car) -> float:
    """Velocidad punta teorica: toda la potencia contra la resistencia."""
    _rpm, hp = car.peak_power()
    if hp <= 0:
        return 240.0
    watts = hp * 735.5
    cda = aero_cda(car)
    speed = (watts * DRIVETRAIN_EFFICIENCY / (0.5 * RHO * cda)) ** (1.0 / 3.0)
    return max(120.0, min(speed * 3.6, 420.0))


def optimal_gearing(
    car,
    target_speed_kmh: float | None = None,
    *,
    first_gear_slip: float = 1.6,
) -> GearingPlan | None:
    """Reparte las relaciones para llegar a ``target_speed_kmh`` en la ultima marcha.

    Se conserva el grupo final y el numero de marchas del coche: la primera se
    calcula para que la fuerza a par maximo apenas supere la traccion disponible
    (``first_gear_slip`` la deja un poco larga para no perder rueda de sobra) y
    las intermedias se reparten en progresion geometrica hasta la ultima.
    """
    ratios = [ratio for ratio in car.gear_ratios() if ratio > 0]
    if len(ratios) < 2 or car.final_drive <= 0:
        return None
    notes: list[str] = []
    target = float(target_speed_kmh or 0.0)
    if target <= 0:
        target = _top_speed_from_power(car)
        notes.append(tr("Velocidad objetivo calculada desde la potencia: {0} km/h", f"{target:.0f}"))
    else:
        notes.append(tr("Velocidad objetivo: {0} km/h", f"{target:.0f}"))

    radius = car.driven_wheel_radius() or 0.33
    shift_rpm = _shift_rpm(car)
    wheels = (target / 3.6) / (2 * math.pi * radius)
    # Relacion total (caja x grupo final) que pone el motor en su regimen de
    # cambio justo a la velocidad pedida; luego se deshace el grupo final.
    total_top = shift_rpm / 60.0 / wheels if wheels > 0 else ratios[-1] * car.final_drive
    ratio_top = max(0.4, min(total_top / car.final_drive, 6.0))

    torque_rpm, torque = car.peak_torque()
    traction = DEFAULT_TYRE_MU * _mass(car) * GRAVITY * _driven_share(car)
    if torque > 0:
        ratio_first = traction * first_gear_slip * radius / (torque * car.final_drive * DRIVETRAIN_EFFICIENCY)
    else:
        ratio_first = ratios[0]
    ratio_first = max(ratio_top * 1.4, min(ratio_first, 7.0))
    if ratio_first <= ratio_top:
        ratio_first = ratio_top * 1.5

    count = len(ratios)
    plan = [
        ratio_first * (ratio_top / ratio_first) ** (index / (count - 1))
        for index in range(count)
    ]
    plan = [round(ratio, 3) for ratio in plan]
    notes.append(
        tr("Primera {0} y ultima {1}: la ultima llega a {2} rpm a la velocidad pedida.",
           f"{plan[0]:.3f}", f"{plan[-1]:.3f}", f"{shift_rpm:.0f}")
    )
    force = _wheel_force(car, torque_rpm, plan[0], torque)
    if force > traction * first_gear_slip * 1.15:
        notes.append(tr("La primera sigue siendo corta: a par maximo pedira mas agarre del disponible."))
    return GearingPlan(
        ratios=tuple(plan),
        final_drive=car.final_drive,
        top_speed_kmh=units.speed_kmh(shift_rpm, plan[-1], car.final_drive, radius),
        first_gear_force_n=force,
        notes=tuple(notes),
    )


def apply_gearing(car, plan: GearingPlan) -> int:
    """Escribe las relaciones propuestas en las marchas que ya existen."""
    applied = 0
    for index, ratio in enumerate(plan.ratios, start=1):
        try:
            car.set_gear(index, ratio)
        except (ValueError, IndexError):
            break
        applied += 1
    return applied


# ------------------------------------------------------------- estilos de setup
STYLE_LABELS: dict[str, str] = {
    "street": "Street",
    "track": "Track",
    "drift": "Drift",
    "gt3": "GT3",
    "drag": "Drag",
    "rally": "Rally",
}

# (fichero, prefijo de seccion o "", clave, modo, valor, etiqueta)
# modo: "set" valor absoluto, "mul" factor sobre el valor actual, "add" delta.
_STYLE_RULES: dict[str, tuple[tuple[str, str, str, str, float, str], ...]] = {
    "street": (
        ("tyres.ini", "FRONT", "PRESSURE_STATIC", "set", 32.0, "presion delantera 32 PSI"),
        ("tyres.ini", "REAR", "PRESSURE_STATIC", "set", 32.0, "presion trasera 32 PSI"),
        ("brakes.ini", "DATA", "FRONT_SHARE", "set", 0.62, "reparto de freno 62% delante"),
        ("suspensions.ini", "", "ARB_FRONT", "mul", 0.75, "barra delantera mas blanda"),
        ("suspensions.ini", "", "ARB_REAR", "mul", 0.75, "barra trasera mas blanda"),
        ("drivetrain.ini", "DIFFERENTIAL", "POWER", "set", 0.35, "bloqueo suave en aceleracion"),
        ("drivetrain.ini", "DIFFERENTIAL", "COAST", "set", 0.15, "bloqueo suave en retencion"),
    ),
    "track": (
        ("tyres.ini", "FRONT", "PRESSURE_STATIC", "set", 28.0, "presion delantera 28 PSI"),
        ("tyres.ini", "REAR", "PRESSURE_STATIC", "set", 29.0, "presion trasera 29 PSI"),
        ("brakes.ini", "DATA", "FRONT_SHARE", "set", 0.66, "reparto de freno 66% delante"),
        ("suspensions.ini", "", "ARB_FRONT", "mul", 1.15, "barra delantera mas firme"),
        ("suspensions.ini", "", "ARB_REAR", "mul", 1.15, "barra trasera mas firme"),
        ("suspensions.ini", "", "SPRING_RATE", "mul", 1.12, "muelles mas firmes"),
        ("suspensions.ini", "", "DAMP_BUMP", "mul", 1.10, "compresion mas firme"),
        ("drivetrain.ini", "DIFFERENTIAL", "POWER", "set", 0.50, "bloqueo medio en aceleracion"),
        ("drivetrain.ini", "DIFFERENTIAL", "PRELOAD", "set", 45.0, "precarga 45 Nm"),
    ),
    "gt3": (
        ("tyres.ini", "FRONT", "PRESSURE_STATIC", "set", 27.0, "presion delantera 27 PSI"),
        ("tyres.ini", "REAR", "PRESSURE_STATIC", "set", 28.0, "presion trasera 28 PSI"),
        ("brakes.ini", "DATA", "FRONT_SHARE", "set", 0.68, "reparto de freno 68% delante"),
        ("suspensions.ini", "", "ARB_FRONT", "mul", 1.25, "barra delantera de competicion"),
        ("suspensions.ini", "", "ARB_REAR", "mul", 1.20, "barra trasera de competicion"),
        ("suspensions.ini", "", "SPRING_RATE", "mul", 1.25, "muelles de competicion"),
        ("suspensions.ini", "", "DAMP_BUMP", "mul", 1.20, "compresion de competicion"),
        ("suspensions.ini", "", "DAMP_REBOUND", "mul", 1.20, "extension de competicion"),
        ("drivetrain.ini", "DIFFERENTIAL", "POWER", "set", 0.30, "bloqueo bajo para trazar"),
        ("drivetrain.ini", "DIFFERENTIAL", "COAST", "set", 0.20, "retencion media"),
        ("suspensions.ini", "", "ROD_LENGTH", "add", -0.015, "altura libre -15 mm"),
    ),
    "drag": (
        ("tyres.ini", "FRONT", "PRESSURE_STATIC", "set", 40.0, "presion delantera alta"),
        ("tyres.ini", "REAR", "PRESSURE_STATIC", "set", 22.0, "presion trasera baja para arrastrar"),
        ("brakes.ini", "DATA", "FRONT_SHARE", "set", 0.55, "reparto de freno 55% delante"),
        ("drivetrain.ini", "DIFFERENTIAL", "POWER", "set", 0.90, "bloqueo alto para lanzar"),
        ("drivetrain.ini", "DIFFERENTIAL", "PRELOAD", "set", 120.0, "precarga 120 Nm"),
        ("drivetrain.ini", "GEARS", "FINAL", "mul", 1.10, "grupo final 10% mas corto"),
        ("suspensions.ini", "REAR", "SPRING_RATE", "mul", 1.15, "trasera mas firme para no hundirse"),
        ("suspensions.ini", "FRONT", "SPRING_RATE", "mul", 0.90, "delantera mas blanda"),
    ),
    "rally": (
        ("tyres.ini", "FRONT", "PRESSURE_STATIC", "set", 30.0, "presion delantera 30 PSI"),
        ("tyres.ini", "REAR", "PRESSURE_STATIC", "set", 30.0, "presion trasera 30 PSI"),
        ("brakes.ini", "DATA", "FRONT_SHARE", "set", 0.64, "reparto de freno 64% delante"),
        ("suspensions.ini", "", "ARB_FRONT", "mul", 0.70, "barras blandas para baches"),
        ("suspensions.ini", "", "ARB_REAR", "mul", 0.70, "barras blandas para baches"),
        ("suspensions.ini", "", "SPRING_RATE", "mul", 0.85, "muelles blandos"),
        ("suspensions.ini", "", "DAMP_BUMP", "mul", 0.85, "compresion blanda"),
        ("suspensions.ini", "", "ROD_LENGTH", "add", 0.035, "altura libre +35 mm"),
        ("drivetrain.ini", "DIFFERENTIAL", "POWER", "set", 0.45, "bloqueo medio"),
    ),
}


def _fraction_scale(value: float) -> float:
    """Los diferenciales se guardan 0-1 o 0-100 segun el coche."""
    return 100.0 if value > 1.01 else 1.0


def _plan_style(car, style: str) -> StyleResult:
    rules = _STYLE_RULES.get(style, ())
    settings = car.advanced_settings()
    index = {(entry.filename.lower(), entry.section.upper(), entry.key.upper()): entry for entry in settings}
    applied: list[str] = []
    skipped: list[str] = []
    for filename, section, key, mode, amount, label_base in rules:
        candidates = [
            entry for (file_name, section_name, entry_key), entry in index.items()
            if file_name == filename.lower()
            and (not section or section_name.startswith(section.upper()))
            and entry_key == key.upper()
        ]
        if not candidates:
            skipped.append(label)
            continue
        # Un coche puede tener FRONT y FRONT_LEFT/FRONT_RIGHT: se marcan para no
        # repetir etiquetas en el resumen.
        specific = len(candidates) > 1
        for entry in candidates:
            label = f"{label_base} ({entry.section})" if specific else label_base
            current = entry.value
            if not math.isfinite(current):
                skipped.append(label)
                continue
            target = current
            if mode == "set":
                # Los bloqueos se guardan 0-1 o 0-100 segun el coche: se respeta su escala.
                target = amount * 100.0 if current > 1.01 else amount
            elif mode == "mul":
                target = current * amount
            elif mode == "add":
                target = current + amount
            if key.upper() in {"POWER", "COAST"}:
                scale = _fraction_scale(current)
                target = min(max(target, 0.0), 0.95 * scale)
            if abs(target - current) < 1e-9:
                continue
            limits = car.setup_range(key)
            if limits:
                low, high, _step = limits
                target = min(max(target, low), high)
            if abs(target - current) < 1e-9 or not car.set_advanced_value(filename, entry.section, key, round(target, 4)):
                skipped.append(label)
            else:
                applied.append(label)
    return StyleResult(tuple(applied), tuple(skipped))


def apply_style(car, style: str) -> StyleResult:
    """Aplica un preset de estilo solo sobre parametros que el coche ya declara."""
    style = str(style).lower()
    if style not in STYLE_LABELS:
        return StyleResult(notes=(tr("Preset desconocido: {0}", style),))
    if style == "drift":
        result = car.apply_drift_preset()
        if not result.applied:
            return StyleResult(notes=(result.reason,))
        return StyleResult(result.applied, result.skipped, (result.reason,))
    result = _plan_style(car, style)
    notes = [tr("Preset {0} aplicado sobre los campos presentes; guarda para escribirlo.", STYLE_LABELS[style])]
    if result.skipped:
        notes.append(tr("{0} ajustes no existen en este coche.", len(result.skipped)))
    return StyleResult(result.applied, result.skipped, tuple(notes))


# ---------------------------------------------------------------- comparacion
_COMPARE_ROWS = (
    "Potencia maxima",
    "Par maximo",
    "Peso",
    "Peso/potencia",
    "0-100 km/h",
    "0-200 km/h",
    "Velocidad punta",
    "Traccion",
    "Marchas",
    "Grupo final",
    "Aceleracion maxima",
)


def compare_cars(cars) -> list[tuple[str, tuple[str, ...]]]:
    """Tabla comparativa: [(fila, (valor coche 1, valor coche 2, ...))]."""
    estimates = [estimate_performance(car) for car in cars]
    rows: list[tuple[str, tuple[str, ...]]] = []

    def add(label: str, values: list[str]) -> None:
        rows.append((label, tuple(values)))

    add(_COMPARE_ROWS[0], [
        f"{car.peak_power()[1]:.0f} CV @ {car.peak_power()[0]:.0f}" if car.peak_power()[1] else "—"
        for car in cars
    ])
    add(_COMPARE_ROWS[1], [
        f"{car.peak_torque()[1]:.0f} Nm @ {car.peak_torque()[0]:.0f}" if car.peak_torque()[1] else "—"
        for car in cars
    ])
    add(_COMPARE_ROWS[2], [f"{_mass(car):.0f} kg" for car in cars])
    add(_COMPARE_ROWS[3], [
        f"{estimate.cv_per_tonne:.0f} CV/t · {estimate.kg_per_cv:.2f} kg/CV" if estimate else "—"
        for estimate in estimates
    ])
    add(_COMPARE_ROWS[4], [
        f"{estimate.zero_100:.2f} s" if estimate and estimate.zero_100 else "> 90 s"
        for estimate in estimates
    ])
    add(_COMPARE_ROWS[5], [
        f"{estimate.zero_200:.2f} s" if estimate and estimate.zero_200 else "> 90 s"
        for estimate in estimates
    ])
    add(_COMPARE_ROWS[6], [
        f"{estimate.top_speed_kmh:.0f} km/h" if estimate else "—" for estimate in estimates
    ])
    add(_COMPARE_ROWS[7], [car.drive_type for car in cars])
    add(_COMPARE_ROWS[8], [str(car.gear_count) for car in cars])
    add(_COMPARE_ROWS[9], [f"{car.final_drive:.3f}" for car in cars])
    add(_COMPARE_ROWS[10], [
        f"{estimate.max_accel_g:.2f} g" if estimate else "—" for estimate in estimates
    ])
    return rows


# ---------------------------------------------------------------- diagnostico
def _range_finding(level_error: tuple[float, float], level_warn: tuple[float, float], value: float) -> str:
    if value <= 0:
        return "error"
    low, high = level_error
    if not low <= value <= high:
        return "error"
    low, high = level_warn
    if not low <= value <= high:
        return "warn"
    return "ok"


def diagnostics(car, estimate: PerformanceEstimate | None = None) -> list[Finding]:
    """Validador avanzado: valores imposibles, sospechosos y conflictos."""
    out: list[Finding] = []
    if car is None:
        return out

    ratios = [ratio for ratio in car.gear_ratios() if ratio > 0]
    if not ratios:
        out.append(Finding("error", "Transmision", tr("No hay relaciones de cambio legibles en drivetrain.ini.")))
    else:
        if any(ratio < 0.5 or ratio > 6.0 for ratio in ratios):
            out.append(Finding("error", "Transmision", tr("Alguna relacion sale del rango fisico (0,5 - 6,0): {0}", ", ".join(f"{r:.3f}" for r in ratios))))
        if any(b >= a for a, b in zip(ratios, ratios[1:])):
            out.append(Finding("warn", "Transmision", tr("Las relaciones no bajan de marcha a marcha: el coche ira raro al cambiar.")))
        spread = ratios[0] / ratios[-1] if ratios[-1] else 0
        if spread and (spread < 2.0 or spread > 8.0):
            out.append(Finding("warn", "Transmision", tr("El salto entre primera y ultima es {0}:1, poco habitual.", f"{spread:.2f}")))
        else:
            out.append(Finding("ok", "Transmision", tr("Relaciones coherentes ({0} marchas).", len(ratios))))

    final = car.final_drive
    final_level = _range_finding((1.5, 6.0), (2.2, 4.6), final)
    out.append(Finding(
        {"ok": "ok", "warn": "warn", "error": "error"}[final_level],
        "Transmision",
        tr("Grupo final {0}.", f"{final:.3f}") if final_level == "ok"
        else tr("Grupo final {0} fuera de lo habitual (2,2 - 4,6).", f"{final:.3f}"),
    ))

    mass = car.mass
    if not mass:
        out.append(Finding("error", "Peso", tr("car.ini no declara MASS: cualquier calculo de prestaciones sera falso.")))
    elif not 400 <= mass <= 2000:
        out.append(Finding("warn", "Peso", tr("Peso {0} kg fuera del rango tipico (400 - 2000).", f"{mass:.0f}")))
    else:
        out.append(Finding("ok", "Peso", tr("Peso {0} kg.", f"{mass:.0f}")))

    limiter = car.limiter
    idle = car.idle_rpm
    if limiter and idle and idle >= limiter:
        out.append(Finding("error", "Motor", tr("El ralenti ({0} rpm) esta por encima del limitador ({1} rpm).", idle, limiter)))
    elif limiter and not 3000 <= limiter <= 12000:
        out.append(Finding("warn", "Motor", tr("Limitador {0} rpm fuera del rango tipico (3000 - 12000).", limiter)))
    else:
        out.append(Finding("ok", "Motor", tr("Limitador {0} rpm · ralenti {1} rpm.", limiter, idle)))

    points = _points(car)
    if len(points) < 2:
        out.append(Finding("error", "Motor", tr("La curva de potencia no tiene puntos suficientes para simular.")))
    else:
        rpms = [rpm for rpm, _torque in points]
        if any(b <= a for a, b in zip(rpms, rpms[1:])):
            out.append(Finding("warn", "Motor", tr("Las rpm de la curva no son crecientes.")))
        peak_rpm, peak_nm = car.peak_torque()
        if peak_nm > 1600:
            out.append(Finding("warn", "Motor", tr("Par maximo {0} Nm: revisa que la escala de la curva sea correcta.", f"{peak_nm:.0f}")))
        else:
            out.append(Finding("ok", "Motor", tr("Curva con {0} puntos · par maximo {1} Nm a {2} rpm.", len(points), f"{peak_nm:.0f}", f"{peak_rpm:.0f}")))

    for entry in car.advanced_settings():
        key = entry.key.upper()
        if key == "FRONT_SHARE" and entry.filename.lower() == "brakes.ini":
            bias_percent = entry.value * 100.0 if entry.value <= 1.01 else entry.value
            if not 40 <= bias_percent <= 85:
                out.append(Finding("warn", "Frenos", tr("Reparto de freno {0} fuera del rango util (40 - 85%).", f"{bias_percent:.0f}%")))
        elif key == "BIAS" and entry.filename.lower() == "brakes.ini" and entry.value and not 400 <= entry.value <= 6000:
            out.append(Finding("warn", "Frenos", tr("Par de frenado {0} Nm fuera del rango tipico.", f"{entry.value:.0f}")))
        elif key == "PRESSURE_STATIC" and entry.filename.lower() == "tyres.ini":
            if entry.value and not 15 <= entry.value <= 50:
                out.append(Finding("warn", "Neumaticos", tr("Presion {0} PSI en {1} fuera de rango.", f"{entry.value:.1f}", entry.section)))
        elif key == "MAX_BOOST" and entry.value and entry.value > 3.5:
            out.append(Finding("warn", "Turbo", tr("MAX_BOOST {0} bar en {1}: el turbo pasa de lo razonable.", f"{entry.value:.2f}", entry.section)))

    for section, key in (("AWD", "FRONT_SHARE"),):
        value = car.awd_value(section, key)
        if value is not None and not 0 <= value <= 1:
            out.append(Finding("error", "Traccion", tr("AWD FRONT_SHARE={0} no esta entre 0 y 1.", value)))

    if estimate is not None:
        if estimate.traction_limited and estimate.zero_100 and estimate.zero_100 < 1.6:
            out.append(Finding("warn", "Prestaciones", tr("La simulacion sale limitada por agarre: la cifra 0-100 depende del neumatico, no de la potencia.")))
        if estimate.top_speed_kmh > 450:
            out.append(Finding("warn", "Prestaciones", tr("Velocidad punta estimada {0} km/h: revisa aero y curva.", f"{estimate.top_speed_kmh:.0f}")))
        elif estimate.top_speed_kmh:
            out.append(Finding("ok", "Prestaciones", tr("Punta estimada {0} km/h · 0-100 {1}.", f"{estimate.top_speed_kmh:.0f}", f"{estimate.zero_100:.2f} s" if estimate.zero_100 else "—")))

    # Detector de conflictos: dos ajustes que se pisan entre ellos.
    if car.power_scale_applied and any(
        entry.key.upper() == "MAX_BOOST" for entry in car.advanced_settings()
    ):
        out.append(Finding("warn", "Conflictos", tr("Has escalado la curva de par y ademas hay turbo: la potencia final es el producto de ambos.")))
    pressures = {
        entry.section.upper(): entry.value
        for entry in car.advanced_settings()
        if entry.filename.lower() == "tyres.ini" and entry.key.upper() == "PRESSURE_STATIC"
    }
    if len(pressures) > 1 and max(pressures.values()) - min(pressures.values()) > 6:
        out.append(Finding("warn", "Neumaticos", tr("Diferencia de mas de 6 PSI entre ejes: el coche estara desequilibrado.")))
    damaged = car.damage
    if damaged.get("turbo_threshold"):
        for turbo in car.turbos():
            if turbo.max_boost > damaged["turbo_threshold"]:
                out.append(Finding("error", "Turbo", tr("MAX_BOOST {0} supera el umbral de dano {1}: AC rompera el turbo.", f"{turbo.max_boost:.2f}", f"{damaged['turbo_threshold']:.2f}")))
    if not any(finding.level != "ok" for finding in out):
        out.append(Finding("ok", "General", tr("Sin conflictos ni valores sospechosos detectados.")))
    return out


def severity_counts(findings) -> tuple[int, int, int]:
    """(correctos, avisos, errores) para el semaforo de diagnostico."""
    ok = sum(1 for finding in findings if finding.level == "ok")
    warn = sum(1 for finding in findings if finding.level == "warn")
    error = sum(1 for finding in findings if finding.level == "error")
    return ok, warn, error


# ------------------------------------------------------------------ informes
def report(car, estimate: PerformanceEstimate | None = None, *, fmt: str = "txt") -> str:
    """Informe del coche en texto o HTML, listo para guardar en disco."""
    findings = diagnostics(car, estimate)
    gears = gear_speeds(car)
    ok, warn, error = severity_counts(findings)
    summary = car.summary()
    if fmt.lower() == "html":
        return _report_html(car, estimate, findings, gears, summary, ok, warn, error)
    return _report_text(car, estimate, findings, gears, summary, ok, warn, error)


def _estimate_rows(estimate: PerformanceEstimate | None) -> list[tuple[str, str]]:
    if estimate is None:
        return [("Prestaciones", "sin datos suficientes")]
    return [
        ("Potencia maxima", f"{estimate.power_hp:.0f} CV a {estimate.power_rpm:.0f} rpm"),
        ("Par maximo", f"{estimate.torque_nm:.0f} Nm a {estimate.torque_rpm:.0f} rpm"),
        ("Peso", f"{estimate.mass_kg:.0f} kg"),
        ("Peso/potencia", f"{estimate.cv_per_tonne:.0f} CV/t · {estimate.kg_per_cv:.2f} kg/CV"),
        ("0-100 km/h", f"{estimate.zero_100:.2f} s" if estimate.zero_100 else "no alcanza"),
        ("0-200 km/h", f"{estimate.zero_200:.2f} s" if estimate.zero_200 else "no alcanza"),
        ("Velocidad punta", f"{estimate.top_speed_kmh:.0f} km/h"),
        ("Aceleracion disponible", f"{estimate.max_accel_g:.2f} g"),
    ]


def _report_text(car, estimate, findings, gears, summary, ok, warn, error) -> str:
    lines = [
        f"QUICK MECHANIC · INFORME DE {car.ui_name}",
        "=" * 60,
        "",
        "-- FICHA TECNICA --",
    ]
    lines += [f"  {label}: {value}" for label, value in summary]
    lines += ["", "-- PRESTACIONES ESTIMADAS --"]
    lines += [f"  {label}: {value}" for label, value in _estimate_rows(estimate)]
    lines += ["", "-- VELOCIDAD POR MARCHA --"]
    for gear in gears:
        lines.append(f"  {gear.gear}ª  relacion {gear.ratio:.3f}   cambio a {gear.shift_kmh:.0f} km/h   par max a {gear.power_kmh:.0f} km/h")
    lines += ["", f"-- DIAGNOSTICO ({ok} correctos · {warn} avisos · {error} errores) --"]
    lines += [f"  {finding.icon} [{finding.area}] {finding.message}" for finding in findings]
    if estimate is not None and estimate.assumptions:
        lines += ["", "-- SUPUESTOS DEL CALCULO --"]
        lines += [f"  - {note}" for note in estimate.assumptions]
    lines += ["", "Generado por Quick Mechanic a partir de los .ini del coche."]
    return "\n".join(lines)


def _report_html(car, estimate, findings, gears, summary, ok, warn, error) -> str:
    def esc(text: str) -> str:
        return (
            str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    rows = "".join(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>" for label, value in summary)
    perf = "".join(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>" for label, value in _estimate_rows(estimate))
    gear_rows = "".join(
        f"<tr><td>{gear.gear}ª</td><td>{gear.ratio:.3f}</td><td>{gear.shift_kmh:.0f} km/h</td>"
        f"<td>{gear.power_kmh:.0f} km/h</td></tr>"
        for gear in gears
    )
    colors = {"ok": "#3ec46d", "warn": "#e0b53c", "error": "#e2554f"}
    findings_rows = "".join(
        f"<li style='color:{colors.get(finding.level, '#ccc')}'>"
        f"{finding.icon} <b>{esc(finding.area)}</b> · {esc(finding.message)}</li>"
        for finding in findings
    )
    notes = "".join(f"<li>{esc(note)}</li>" for note in (estimate.assumptions if estimate else ()))
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Quick Mechanic · {esc(car.ui_name)}</title>
<style>
 body {{ background:#141416; color:#e8e6e1; font-family:system-ui,Segoe UI,sans-serif; padding:28px; }}
 h1 {{ color:#d8b45a; margin:0 0 4px 0; }}
 h2 {{ color:#d8b45a; font-size:15px; letter-spacing:1px; text-transform:uppercase; margin:26px 0 8px; }}
 table {{ border-collapse:collapse; width:100%; max-width:860px; }}
 th {{ text-align:left; color:#9a968e; font-weight:400; padding:3px 14px 3px 0; width:280px; }}
 td {{ padding:3px 0; }}
 ul {{ list-style:none; padding:0; max-width:860px; }}
 li {{ padding:3px 0; }}
 .badge {{ color:#9a968e; font-size:12px; }}
</style></head><body>
<h1>{esc(car.ui_name)}</h1>
<p class="badge">Carpeta {esc(car.name)} · {esc(car.drive_type)} · {esc(summary[0][1])}</p>
<h2>Ficha tecnica</h2><table>{rows}</table>
<h2>Prestaciones estimadas</h2><table>{perf}</table>
<h2>Velocidad por marcha</h2>
<table><tr><th>Marcha</th><th>Relacion</th><th>Cambio</th><th>Par maximo</th></tr>{gear_rows}</table>
<h2>Diagnostico · {ok} correctos · {warn} avisos · {error} errores</h2><ul>{findings_rows}</ul>
<h2>Supuestos del calculo</h2><ul>{notes}</ul>
<p class="badge">Generado por Quick Mechanic a partir de los .ini del coche.</p>
</body></html>"""


# ------------------------------------------------------------ estadisticas
def library_stats(cars, meta_cache: dict | None = None, favorites=()) -> list[tuple[str, str]]:
    """Estadisticas globales de la biblioteca usando solo metadatos ya leidos."""
    meta_cache = meta_cache or {}
    total = len(cars)
    editable = sum(1 for car in cars if car.editable)
    brands: dict[str, int] = {}
    classes: dict[str, int] = {}
    countries: dict[str, int] = {}
    specs_total = 0
    for car in cars:
        meta = meta_cache.get(car.folder)
        if meta is None:
            continue
        brand = (meta.brand or "").strip()
        if brand:
            brands[brand] = brands.get(brand, 0) + 1
        category = (meta.car_class or "").strip()
        if category:
            classes[category] = classes.get(category, 0) + 1
        country = (getattr(meta, "country", "") or "").strip()
        if country:
            countries[country] = countries.get(country, 0) + 1
        specs_total += len(meta.specs or ())
    top_brand = max(brands.items(), key=lambda item: item[1]) if brands else ("—", 0)
    top_class = max(classes.items(), key=lambda item: item[1]) if classes else ("—", 0)
    return [
        ("Coches en la biblioteca", str(total)),
        ("Editables (carpeta data)", f"{editable} de {total}"),
        ("Marcas distintas", str(len(brands))),
        ("Categorias distintas", str(len(classes))),
        ("Paises distintos", str(len(countries))),
        ("Marca mas repetida", f"{top_brand[0]} ({top_brand[1]})"),
        ("Categoria mas comun", f"{top_class[0]} ({top_class[1]})"),
        ("Favoritos", str(len(favorites))),
        ("Datos de ficha leidos", f"{specs_total} campos"),
    ]
