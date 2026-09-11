"""Robust (quantile) Model Predictive Control driven by a probabilistic forecast.

The deterministic MPC plans against a single point forecast: the recent-mean ET0 with no rain.
That ignores forecast *uncertainty*.
This controller instead draws an ensemble of near-term weather trajectories from the empirical forecaster (weather.forecast.EmpiricalForecaster) and plans against a chosen upper quantile of the ensemble demand.
Planning for the risk that crop water demand runs higher than the mean makes the controller pre-empt stress rather than be caught short - a standard robust-MPC use of a probabilistic forecast.

It reuses the linear program unchanged: only the forecast hook differs, exactly as the perfect-foresight oracle reuses it. ``demand_quantile`` selects the risk posture - 0.5 recovers a mean forecast, higher values are more conservative.
Rain is held at zero (the drought-robust assumption), so the ensemble informs demand, not opportunistic rain.
"""

from __future__ import annotations

import numpy as np

from ..config.schema import Scenario
from ..weather.forecast import EmpiricalForecaster
from .mpc import MPCController


class StochasticMPCController(MPCController):
    """MPC that plans against an upper quantile of an ensemble demand forecast."""

    def __init__(self, scenario: Scenario, horizon: int = 45, n_scenarios: int = 20, demand_quantile: float = 0.7, forecast_window: int = 20, seed: int = 0):
        super().__init__(scenario, horizon=horizon)

        if not 0.0 < demand_quantile < 1.0:
            raise ValueError("demand_quantile must be in (0, 1)")

        self.name = "stochastic_mpc"
        self.n_scenarios = int(n_scenarios)
        self.demand_quantile = float(demand_quantile)
        self._seed = int(seed)
        self._fc_window = int(forecast_window)
        self._fc = EmpiricalForecaster(window=self._fc_window, seed=self._seed)

    def reset(self) -> None:
        super().reset()
        self._fc = EmpiricalForecaster(window=self._fc_window, seed=self._seed)

    def plan_day(self, day_index: int, depletions: dict[str, float], reserve_available_m3: float, et0_today: float, rain_today: float = 0.0) -> None:
        self._fc.observe(et0_today, rain_today)
        super().plan_day(day_index, depletions, reserve_available_m3, et0_today, rain_today)

    def _forecast(self, day_index: int, et0_today: float) -> tuple[list[float], list[float]]:
        """Upper-quantile ET0 across the ensemble; drought-robust zero rain."""
        scen = self._fc.scenarios(self.horizon, self.n_scenarios)
        et0_mat = np.array([s[0] for s in scen])  # (n, H)
        et0_q = np.quantile(et0_mat, self.demand_quantile, axis=0).tolist()

        return et0_q, [0.0] * self.horizon
