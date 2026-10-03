"""Perfiles de ajuste orientativo para drift, aplicados solo a valores presentes."""
from __future__ import annotations

from .car_data import DriftPresetResult


def apply(car) -> DriftPresetResult:
    """Prepara los cambios del preset para el coche; el llamante decide guardarlos."""
    return car.apply_drift_preset()


__all__ = ["DriftPresetResult", "apply"]
