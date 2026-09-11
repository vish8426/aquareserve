"""Perfect-foresight oracle: the MPC given the actual future weather.

The oracle is the MPC controller with one change - its horizon forecast is the *real* future weather (ET0 and rain) rather than a recent-mean estimate.
It still re-solves daily on the true engine state (closed-loop), so it dominates the realistic MPC by construction.
The gap between the two is exactly the yield gained from knowing the future, i.e. the value of a perfect forecast (an upper bound the realistic controllers cannot exceed).
See ADR-007.
"""

from __future__ import annotations

import pandas as pd

from ..config.schema import Scenario
from ..weather import columns as C
from .mpc import MPCController


class OracleController(MPCController):
    """MPC with perfect foresight (actual future weather over the horizon)."""

    def __init__(self, scenario: Scenario, weather: pd.DataFrame,
                 planting_date: str = "2000-05-01", horizon: int = 45):
        super().__init__(scenario, horizon=horizon)
        self.name = "oracle"
        planting = pd.Timestamp(planting_date)
        big_t = max(self.curves[z.id].total_days for z in scenario.farm.zones)
        window = weather.loc[planting : planting + pd.Timedelta(days=big_t - 1)]
        self._et0 = window[C.ET0].to_numpy()
        self._rain = window[C.RAIN].to_numpy()

    def _forecast(self, day_index: int, et0_today: float) -> tuple[list[float], list[float]]:
        n = len(self._et0)
        et0, rain = [], []
        for t in range(self.horizon):
            idx = day_index + t
            if 0 <= idx < n:
                et0.append(float(self._et0[idx]))
                rain.append(float(self._rain[idx]))
            else:
                et0.append(float(self._et0[-1]) if n else et0_today)
                rain.append(0.0)
        return et0, rain
