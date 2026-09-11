"""Probabilistic short-horizon weather forecaster.

The realistic MPC plans against a single guessed future.
A more honest input is a *distribution* of futures.
This forecaster keeps a rolling window of the most recent observed weather and on request, produces an ensemble of horizon length trajectories by resampling recent (ET0, rain) days.
Under a dry recent spell most sampled futures are dry; after rain they are wetter.
The stochastic MPC (controllers.stochastic_mpc) optimises today's decision against this ensemble rather than one point forecast.

It is deliberately simple (empirical resampling), not a climate model, enough to give the controller a sense of the range of plausible near-term weather.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class EmpiricalForecaster:
    """Resamples the recent observed weather to produce ensemble forecasts."""

    def __init__(self, window: int = 20, seed: int = 0):

        if window < 1:
            raise ValueError("window must be >= 1")

        # (et0, rain)
        self._win: deque[tuple[float, float]] = deque(maxlen=window)  
        self._rng = np.random.default_rng(seed)

    def observe(self, et0: float, rain: float) -> None:
        self._win.append((float(et0), float(rain)))

    def scenarios(self, horizon: int, n: int) -> list[tuple[list[float], list[float]]]:

        """Return ``n`` (et0[H], rain[H]) trajectories resampled from recent weather."""

        if not self._win:
            return [([0.0] * horizon, [0.0] * horizon) for _ in range(n)]

        arr = np.array(self._win)  # (m, 2)
        out = []

        for _ in range(n):
            idx = self._rng.integers(0, len(arr), size=horizon)
            out.append((arr[idx, 0].tolist(), arr[idx, 1].tolist()))

        return out

    def mean(self, horizon: int) -> tuple[list[float], list[float]]:
        """Mean ET0 and rain over the recent window, repeated across the horizon."""
        if not self._win:
            return [0.0] * horizon, [0.0] * horizon

        arr = np.array(self._win)
        
        return [float(arr[:, 0].mean())] * horizon, [float(arr[:, 1].mean())] * horizon
