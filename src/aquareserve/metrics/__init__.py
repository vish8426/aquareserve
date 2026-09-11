"""Experiment metrics and cost/ROI model.

Public API:
    compute_metrics(result, scenario) -> FarmMetrics       (agronomic + water)
    FarmMetrics, ZoneMetrics
    system_capex, annual_benefit, npv, evaluate            (economics)
    ControllerEconomics, dam_capacity_to_match
"""

from .agronomic import FarmMetrics, ZoneMetrics, compute_metrics
from .economic import (
    ControllerEconomics,
    annual_benefit,
    dam_capacity_to_match,
    evaluate,
    npv,
    production_value,
    system_capex,
)

__all__ = [
    "compute_metrics",
    "FarmMetrics",
    "ZoneMetrics",
    "ControllerEconomics",
    "system_capex",
    "production_value",
    "annual_benefit",
    "npv",
    "evaluate",
    "dam_capacity_to_match",
]
