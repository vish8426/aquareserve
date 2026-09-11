"""Model Predictive Control for reserve allocation, plus the forecast hook the perfect-foresight oracle reuses.

Each day the MPC solves a finite-horizon linear program that allocates the finite reserve across every zone and horizon day to minimise yield-weighted water stress, subject to the reserve budget and per-zone rate limits, then applies only the first day's plan and re-solves tomorrow with updated state (receding horizon).

Formulation (variables: irrigation u[z,t] and stress slack s[z,t]):

    minimise   sum_{z,t}  value_z * Ky(z,t) * s[z,t]
    subject to Dr[z,t]  = Dr0_z + sum_{k<=t}(ETc[z,k] - rain[k] - u[z,k])
               s[z,t]  >= Dr[z,t] - RAW_z ,   s[z,t] >= 0
               0 <= u[z,t] <= max_rate_z
               sum_{z,t} u[z,t]*area_z*10/eff_z  <= reserve budget over the horizon

The only thing that separates the realistic MPC from the oracle is the *forecast* (``_forecast``): the MPC uses a recent-mean ET0 with zero rain, while the oracle substitutes the actual future weather.
Linear MPC is solved with scipy.optimize.linprog (HiGHS) for reliability and CI-safety.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from scipy.optimize import linprog

from ..config.schema import ReserveStrategy, Scenario
from ..models import CropCurve, ReserveModel, taw_from_soil
from .base import ZoneControlContext

_M3_PER_MM_HA = 10.0


class MPCController:
    """Receding-horizon linear MPC over the shared reserve."""

    def __init__(self, scenario: Scenario, horizon: int = 45, forecast_window: int = 10):
        if horizon < 2:
            raise ValueError("horizon must be >= 2")

        self.scenario = scenario
        self.horizon = int(horizon)
        self.name = "mpc"
        self._win: deque[float] = deque(maxlen=forecast_window)
        self._today: dict[str, float] = {}
        self.curves: dict[str, CropCurve] = {}
        self.taw: dict[str, float] = {}
        self.raw: dict[str, float] = {}

        for z in scenario.farm.zones:
            crop = scenario.crops[z.crop]

            self.curves[z.id] = CropCurve(crop)

            taw = taw_from_soil(z.soil.total_available_water_mm_per_m, crop.root_depth.max_m)

            self.taw[z.id] = taw
            self.raw[z.id] = crop.depletion_fraction_p * taw

        self._reserve = ReserveModel(scenario.farm.reserve)
        self.baseflow_m3 = self._reserve.baseflow()

    def reset(self) -> None:
        self._win.clear()
        self._today = {}

    def _forecast(self, day_index: int, et0_today: float) -> tuple[list[float], list[float]]:
        """Return (et0[H], rain[H]) forecasts. MPC: recent-mean ET0, zero rain."""
        et0_f = sum(self._win) / len(self._win)

        return [et0_f] * self.horizon, [0.0] * self.horizon

    def plan_day(self, day_index: int, depletions: dict[str, float], reserve_available_m3: float, et0_today: float, rain_today: float = 0.0) -> None:
        """Solve the horizon LP for the current state; cache today's per-zone plan."""
        self._win.append(float(et0_today))

        et0_fc, rain_fc = self._forecast(day_index, float(et0_today))
        h = len(et0_fc)

        zones = [
            z for z in self.scenario.farm.zones

            if z.strategy != ReserveStrategy.RAINFED and 0 <= day_index < self.curves[z.id].total_days
        ]

        if not zones:
            self._today = {}
            return

        nz = len(zones)
        nvar = 2 * nz * h

        def ui(zi, t):
            return zi * h + t

        def si(zi, t):
            return nz * h + zi * h + t

        c = np.zeros(nvar)
        bounds = [(0.0, None)] * nvar
        a_ub, b_ub = [], []

        budget_row = np.zeros(nvar)
        budget = reserve_available_m3 + sum(self.baseflow_m3 + self._reserve.capture_from_rain(rain_fc[t]) for t in range(h))

        for zi, z in enumerate(zones):
            crop = self.scenario.crops[z.crop]
            curve = self.curves[z.id]
            raw = self.raw[z.id]
            dr0 = depletions[z.id]
            gross_per_mm = z.area_ha * _M3_PER_MM_HA / z.irrigation_efficiency
            cum_net = 0.0

            for t in range(h):
                d = min(day_index + t, curve.total_days - 1)
                etc_t = curve.crop_demand_mm(d, et0_fc[t])
                ky_t = crop.yield_response.by_stage.get(curve.stage(d), crop.yield_response.seasonal)
                cum_net += etc_t - rain_fc[t]
                bounds[ui(zi, t)] = (0.0, z.max_application_rate_mm_per_day)
                c[si(zi, t)] = crop.reference_yield_t_per_ha * ky_t
                budget_row[ui(zi, t)] = gross_per_mm
                row = np.zeros(nvar)

                for k in range(t + 1):
                    row[ui(zi, k)] = -1.0

                row[si(zi, t)] = -1.0

                a_ub.append(row)
                b_ub.append(raw - dr0 - cum_net)

        a_ub.append(budget_row)
        b_ub.append(budget)

        res = linprog(c, A_ub=np.array(a_ub), b_ub=np.array(b_ub), bounds=bounds, method="highs")

        self._today = {}

        if res.success:

            for zi, z in enumerate(zones):
                self._today[z.id] = max(0.0, float(res.x[ui(zi, 0)]))

    def request_mm(self, ctx: ZoneControlContext) -> float:
        return self._today.get(ctx.zone_id, 0.0)
