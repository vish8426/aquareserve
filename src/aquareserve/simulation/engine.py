"""Closed-loop, multi-zone simulation engine.

Runs a whole farm over a season for one controller.
Each day, every active zones crop demand is computed, the controller requests irrigation and the shared finite reserve is allocated across zones (in a priority order) subject to each zones application-rate limit and irrigation efficiency.
Irrigation is applied to the soil water balance, yield accumulates and the reserve is updated once (capture, bore inflow, evaporation, total withdrawal, spill).

This closes the loop of the whole project: weather -> soil -> crop -> controller -> reserve -> irrigation -> soil, for any controller implementing the controller interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config.schema import Scenario
from ..controllers.base import Controller, ZoneControlContext
from ..models import (
    CropCurve,
    ReserveModel,
    SoilWaterBalance,
    YieldAccumulator,
    YieldResult,
    taw_from_soil,
)
from ..weather import columns as C

_M3_PER_MM_HA = 10.0


@dataclass
class SimulationResult:
    """Outputs of one closed-loop run."""

    controller: str

    # per zone per day: etc/eta/irrig/depletion/ks
    zone_days: pd.DataFrame

    # per day: volume/capture/evaporation/withdrawal/spill  
    reserve: pd.DataFrame  
    yields: dict[str, YieldResult] = field(default_factory=dict)

    def irrigation_m3(self, zone_id: str | None = None) -> float:
        df = self.zone_days

        if zone_id is not None:
            df = df[df["zone_id"] == zone_id]

        return float(df["irrig_m3"].sum())

    def reserve_survival_days(self) -> int:
        """Number of days the reserve held usable water (volume > 1 m3)."""
        return int((self.reserve["volume_m3"] > 1.0).sum())


class SimulationEngine:
    """Run a scenario over a season for a given controller."""

    def __init__(self, scenario: Scenario, weather: pd.DataFrame, planting_date: str = "2000-05-01"):
        self.scenario = scenario
        self.weather = weather
        self.planting = pd.Timestamp(planting_date)

        # Allocation priority: order zones as configured (smart controllers reorder).
        self.priority = [z.id for z in scenario.farm.zones]

    def run(self, controller: Controller) -> SimulationResult:
        zones = {z.id: z for z in self.scenario.farm.zones}
        crops = {zid: self.scenario.crops[z.crop] for zid, z in zones.items()}
        curves = {zid: CropCurve(crops[zid]) for zid in zones}

        taws = {
            zid: taw_from_soil(z.soil.total_available_water_mm_per_m, crops[zid].root_depth.max_m)
            for zid, z in zones.items()
        }

        swbs = {
            zid: SoilWaterBalance(taws[zid], crops[zid].depletion_fraction_p, zones[zid].soil.initial_depletion_fraction * taws[zid])
            for zid in zones
        }

        yields = {zid: YieldAccumulator(crops[zid]) for zid in zones}
        days_since_irr = {zid: 999 for zid in zones}
        season_len = {zid: crops[zid].stage_days.total for zid in zones}
        reserve = ReserveModel(self.scenario.farm.reserve)
        controller.reset()

        end = self.planting + pd.Timedelta(days=max(season_len.values()) - 1)
        window = self.weather.loc[self.planting : end]

        zone_rows: list[dict] = []
        reserve_rows: list[dict] = []

        for date, wx in window.iterrows():
            rain, et0 = float(wx[C.RAIN]), float(wx[C.ET0])
            available = reserve.available_for_withdrawal(rain, et0)
            allocated = 0.0

            # Farm-level controllers (e.g. MPC, oracle) plan the whole day up front.
            if hasattr(controller, "plan_day"):
                day_index = (date - self.planting).days
                controller.plan_day(day_index, {zid: swbs[zid].dr for zid in zones}, available, et0, rain)

            for zid in self.priority:
                day = (date - self.planting).days

                if day < 0 or day >= season_len[zid]:
                    continue

                z, curve, swb = zones[zid], curves[zid], swbs[zid]
                etc = curve.crop_demand_mm(day, et0)
                stage = curve.stage(day)
                yr = crops[zid].yield_response

                ctx = ZoneControlContext(
                    zone_id=zid, day_in_season=day, stage=stage,
                    depletion_mm=swb.dr, raw_mm=swb.raw_mm, taw_mm=swb.taw,
                    et0_mm=et0, crop_et_mm=etc, days_since_irrigation=days_since_irr[zid],
                    max_application_rate_mm_per_day=z.max_application_rate_mm_per_day,
                    strategy=z.strategy, stage_ky=yr.by_stage.get(stage, yr.seasonal),
                )

                req_mm = min(max(0.0, controller.request_mm(ctx)), z.max_application_rate_mm_per_day)
                gross_needed = req_mm * z.area_ha * _M3_PER_MM_HA / z.irrigation_efficiency
                actual_gross = min(gross_needed, max(0.0, available - allocated))
                net_mm = actual_gross * z.irrigation_efficiency / (z.area_ha * _M3_PER_MM_HA)
                allocated += actual_gross

                step = swb.step(rain_mm=rain, crop_et_mm=etc, irrigation_mm=net_mm)
                yields[zid].add_day(curve.stage(day), etc, step.actual_et_mm)
                days_since_irr[zid] = 0 if net_mm > 1e-9 else days_since_irr[zid] + 1

                zone_rows.append({
                    "date": date, "zone_id": zid, "stage": stage.value,
                    "etc_mm": etc, "eta_mm": step.actual_et_mm, "irrig_mm": net_mm,
                    "irrig_m3": actual_gross, "depletion_mm": step.depletion_mm,
                    "ks": step.stress_coefficient,
                })

            rstep = reserve.step(rain, et0, allocated)
            
            reserve_rows.append({
                "date": date, "volume_m3": rstep.volume_m3, "capture_m3": rstep.capture_m3,
                "baseflow_m3": rstep.baseflow_m3, "evaporation_m3": rstep.evaporation_m3,
                "withdrawal_m3": rstep.withdrawal_m3, "spill_m3": rstep.spill_m3,
                "fraction_full": rstep.fraction_full,
            })

        return SimulationResult(
            controller=getattr(controller, "name", type(controller).__name__),
            zone_days=pd.DataFrame(zone_rows).set_index("date"),
            reserve=pd.DataFrame(reserve_rows).set_index("date"),
            yields={zid: yields[zid].result() for zid in zones},
        )
