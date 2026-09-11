"""Agronomic and water metrics from a simulation run.

Turns a :class:`SimulationResult` into the numbers the comparison study reports:
relative and absolute yield, production, irrigation applied, water use efficiency, stress-days and reserve survival.
Economic metrics (payback, NPV) live in the economic module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.schema import Scenario
from ..simulation import SimulationResult

_T_TO_KG = 1000.0


@dataclass
class ZoneMetrics:
    zone_id: str
    crop: str
    area_ha: float

    # Ya/Ym in [0, 1]
    relative_yield: float  
    yield_t_ha: float

    # yield_t_ha * area_ha
    production_t: float  

    # total net depth applied
    irrigation_mm: float  

    # total gross drawn from the reserve
    irrigation_m3: float  
    stress_days: int

    # production per m3 of irrigation (None if rainfed)
    wue_kg_per_m3: float | None  


@dataclass
class FarmMetrics:
    controller: str
    zones: list[ZoneMetrics] = field(default_factory=list)
    total_production_t: float = 0.0
    total_irrigation_m3: float = 0.0
    reserve_survival_days: int = 0
    reserve_end_m3: float = 0.0

    def as_rows(self) -> list[dict]:
        return [z.__dict__ for z in self.zones]


def compute_metrics(result: SimulationResult, scenario: Scenario) -> FarmMetrics:
    zones = {z.id: z for z in scenario.farm.zones}
    zd = result.zone_days
    zone_metrics: list[ZoneMetrics] = []

    for zid, zone in zones.items():
        sub = zd[zd["zone_id"] == zid]
        yres = result.yields[zid]
        irrig_mm = float(sub["irrig_mm"].sum())
        irrig_m3 = float(sub["irrig_m3"].sum())
        production_t = yres.actual_yield_t_ha * zone.area_ha
        wue = (production_t * _T_TO_KG / irrig_m3) if irrig_m3 > 1e-9 else None

        zone_metrics.append(
            ZoneMetrics(
                zone_id=zid,
                crop=zone.crop,
                area_ha=zone.area_ha,
                relative_yield=yres.relative_yield,
                yield_t_ha=yres.actual_yield_t_ha,
                production_t=production_t,
                irrigation_mm=irrig_mm,
                irrigation_m3=irrig_m3,
                stress_days=int((sub["ks"] < 0.999).sum()),
                wue_kg_per_m3=wue,
            )
        )

    reserve_end = float(result.reserve["volume_m3"].iloc[-1]) if len(result.reserve) else 0.0
    
    return FarmMetrics(
        controller=result.controller,
        zones=zone_metrics,
        total_production_t=sum(z.production_t for z in zone_metrics),
        total_irrigation_m3=sum(z.irrigation_m3 for z in zone_metrics),
        reserve_survival_days=result.reserve_survival_days(),
        reserve_end_m3=reserve_end,
    )
