"""Shared soil-water process step used by both the EKF and the EnKF.

Keeping the process model in one place guarantees the two estimators predict with *identical* physics, so any difference between them comes from the filtering method (analytic linearisation vs a stochastic ensemble), not from divergent models.
"""

from __future__ import annotations


def stress_coefficient(dr: float, taw: float, raw: float) -> float:
    """FAO-56 water-stress coefficient Ks for a depletion dr."""
    if dr <= raw:
        return 1.0

    return max(0.0, min(1.0, (taw - dr) / (taw - raw)))


def soil_water_step(dr: float, taw: float, raw: float, rain_mm: float, crop_et_mm: float, irrigation_mm: float = 0.0) -> float:
    """Advance root-zone depletion one day (mirrors models.SoilWaterBalance.step)."""
    etc = max(0.0, crop_et_mm)
    eta = stress_coefficient(dr, taw, raw) * etc
    water_in = max(0.0, rain_mm) + max(0.0, irrigation_mm)
    drainage = max(0.0, water_in - eta - dr)
    
    return min(max(0.0, dr - water_in + eta + drainage), taw)
