"""Unidades y fisica basica.

AC guarda todo en unidades del sistema internacional (N/m, N·s/m, Nm, kg,
metros) pero en el garaje se piensa en N/mm, N·s/mm, CV, PSI o km/h. Aqui
estan todas las conversiones en un solo sitio para que la interfaz muestre
numeros que se entienden y los .ini reciban lo que AC espera.
"""
from __future__ import annotations

import math

__all__ = [
    "KMH_PER_MPS",
    "spring_to_nmm",
    "spring_from_nmm",
    "damper_to_nsmm",
    "damper_from_nsmm",
    "kw_from_torque",
    "hp_from_kw",
    "hp_from_torque",
    "torque_at_rpm",
    "wheel_rpm",
    "speed_kmh",
    "power_weight",
    "bar_to_psi",
    "psi_to_bar",
    "deg",
]

KMH_PER_MPS = 3.6
_W_PER_HP = 745.6998715822702


# ------------------------------------------------------------------ suspension
def spring_to_nmm(n_per_m: float) -> float:
    """N/m (como lo guarda AC) -> N/mm (como se habla en el garaje)."""
    return n_per_m / 1000.0


def spring_from_nmm(n_per_mm: float) -> float:
    return n_per_mm * 1000.0


def damper_to_nsmm(n_sec_per_m: float) -> float:
    """N·s/m (AC) -> N·s/mm."""
    return n_sec_per_m / 1000.0


def damper_from_nsmm(n_sec_per_mm: float) -> float:
    return n_sec_per_mm * 1000.0


# --------------------------------------------------------------------- motor
def kw_from_torque(torque_nm: float, rpm: float) -> float:
    """Potencia (kW) a partir del par y las revoluciones: P = T · ω."""
    return torque_nm * rpm * 2.0 * math.pi / 60.0 / 1000.0


def hp_from_kw(kw: float) -> float:
    return kw * 1000.0 / _W_PER_HP


def hp_from_torque(torque_nm: float, rpm: float) -> float:
    return hp_from_kw(kw_from_torque(torque_nm, rpm))


def torque_at_rpm(points: list[tuple[float, float]], rpm: float) -> float:
    """Par interpolado linealmente en la curva de potencia (extremos planos)."""
    if not points:
        return 0.0
    ordered = sorted(points)
    if rpm <= ordered[0][0]:
        return ordered[0][1]
    if rpm >= ordered[-1][0]:
        return ordered[-1][1]
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        if x0 <= rpm <= x1:
            if x1 == x0:
                return y1
            ratio = (rpm - x0) / (x1 - x0)
            return y0 + (y1 - y0) * ratio
    return ordered[-1][1]


def power_weight(mass_kg: float, hp: float) -> tuple[float, float]:
    """(CV por tonelada, kg por CV)."""
    if mass_kg <= 0 or hp <= 0:
        return (0.0, 0.0)
    return (hp / (mass_kg / 1000.0), mass_kg / hp)


# ------------------------------------------------------------------ transmision
def wheel_rpm(rpm: float, gear_ratio: float, final_drive: float) -> float:
    total = gear_ratio * final_drive
    return rpm / total if total else 0.0


def speed_kmh(rpm: float, gear_ratio: float, final_drive: float, radius_m: float) -> float:
    """Velocidad teorica (km/h) para un regimen, una marcha y un radio de rueda."""
    if radius_m <= 0:
        return 0.0
    metres_per_minute = wheel_rpm(rpm, gear_ratio, final_drive) * 2.0 * math.pi * radius_m
    return metres_per_minute * 60.0 / 1000.0


def rpm_at_speed(speed: float, gear_ratio: float, final_drive: float, radius_m: float) -> float:
    """Inversa de speed_kmh: regimen para una velocidad dada."""
    if radius_m <= 0:
        return 0.0
    metres_per_minute = speed * 1000.0 / 60.0
    return (
        metres_per_minute / (2.0 * math.pi * radius_m) * gear_ratio * final_drive
    )


# ---------------------------------------------------------------- neumaticos
def bar_to_psi(bar: float) -> float:
    return bar * 14.503773773


def psi_to_bar(psi: float) -> float:
    return psi / 14.503773773


def deg(radians: float) -> float:
    return math.degrees(radians)
