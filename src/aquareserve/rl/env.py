"""Gymnasium environment over the finite-reserve irrigation problem (optional path).

Wraps the AquaReserve digital twin as a standard ``gymnasium.Env`` so off-the-shelf deep RL algorithms (e.g. Stable-Baselines3 PPO via scripts/train_rl_sb3.py) can be trained against it.
One episode is one season; each step is one day.
The action is a per-zone irrigation fraction of that zone's maximum rate; the observation stacks per-zone soil and stage state with the global reserve level and demand.
The reward is the daily gain in yield-weighted, value-scaled water satisfaction, so cumulative reward tracks farmgate production value.

The environment mirrors the daily loop of simulation.engine using the same model primitives (CropCurve, SoilWaterBalance, ReserveModel).
It exists for the deep RL comparison only; the in-repo CI-safe RL policy is trained by rl.cem directly on the engine, which keeps the graded comparison identical across all controllers.
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from ..config.schema import ReserveStrategy, Scenario
from ..models import CropCurve, ReserveModel, SoilWaterBalance, taw_from_soil
from ..weather import columns as C

_M3_PER_MM_HA = 10.0


class ReserveIrrigationEnv(gym.Env):
    """Season-long, day-stepped irrigation control over the shared reserve."""

    metadata = {"render_modes": []}

    def __init__(self, scenario: Scenario, weather: pd.DataFrame, planting_date: str = "2000-05-01"):
        
        super().__init__()

        self.scenario = scenario
        self.weather = weather
        self.planting = pd.Timestamp(planting_date)
        self.zones = [z for z in scenario.farm.zones if z.strategy != ReserveStrategy.RAINFED]
        self.nz = len(self.zones)
        self._crops = {z.id: scenario.crops[z.crop] for z in self.zones}
        self._curves = {z.id: CropCurve(self._crops[z.id]) for z in self.zones}

        self._taw = {
            z.id: taw_from_soil(z.soil.total_available_water_mm_per_m, self._crops[z.id].root_depth.max_m)

            for z in self.zones
        }

        vmax = max(c.reference_yield_t_per_ha * c.price_per_t for c in self._crops.values()) or 1.0

        self._value = {z.id: self._crops[z.id].reference_yield_t_per_ha 
                       * self._crops[z.id].price_per_t / vmax for z in self.zones}

        self._season = max(self._crops[z.id].stage_days.total for z in self.zones)
        self._cap = ReserveModel(scenario.farm.reserve).capacity or 1.0

        self.action_space = spaces.Box(0.0, 1.0, shape=(self.nz,), dtype=np.float32)

        obs_dim = self.nz * 4 + 3

        self.observation_space = spaces.Box(-5.0, 5.0, shape=(obs_dim,), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)

        self._swb = {
            z.id: SoilWaterBalance(self._taw[z.id], self._crops[z.id].depletion_fraction_p, z.soil.initial_depletion_fraction * self._taw[z.id])

            for z in self.zones
        }

        self._reserve = ReserveModel(self.scenario.farm.reserve)
        self._days_since = {z.id: 999 for z in self.zones}
        self._day = 0

        return self._obs(0.0, 0.0), {}

    def _obs(self, et0: float, rain: float) -> np.ndarray:
        feats = []

        for z in self.zones:
            swb, curve = self._swb[z.id], self._curves[z.id]
            d = min(self._day, curve.total_days - 1)
            yr = self._crops[z.id].yield_response
            ky = yr.by_stage.get(curve.stage(d), yr.seasonal)
            feats += [swb.dr / (swb.taw or 1.0), max(0.0, (swb.dr - swb.raw_mm) / (swb.taw or 1.0)), ky, min(1.0, self._days_since[z.id] / 10.0)]

        feats += [self._reserve.fraction_full, et0 / 8.0, self._day / self._season]

        return np.array(feats, dtype=np.float32)

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=float), 0.0, 1.0)
        date = self.planting + pd.Timedelta(days=self._day)
        wx = self.weather.loc[date]
        rain, et0 = float(wx[C.RAIN]), float(wx[C.ET0])
        available = self._reserve.available_for_withdrawal(rain, et0)
        allocated = reward = 0.0

        for i, z in enumerate(self.zones):

            if self._day >= self._crops[z.id].stage_days.total:
                continue

            swb, curve = self._swb[z.id], self._curves[z.id]
            etc = curve.crop_demand_mm(self._day, et0)
            req_mm = action[i] * z.max_application_rate_mm_per_day
            gross = min(req_mm * z.area_ha * _M3_PER_MM_HA / z.irrigation_efficiency, max(0.0, available - allocated))

            net_mm = gross * z.irrigation_efficiency / (z.area_ha * _M3_PER_MM_HA)
            allocated += gross

            s = swb.step(rain_mm=rain, crop_et_mm=etc, irrigation_mm=net_mm)

            self._days_since[z.id] = 0 if net_mm > 1e-9 else self._days_since[z.id] + 1

            yr = self._crops[z.id].yield_response
            ky = yr.by_stage.get(curve.stage(self._day), yr.seasonal)

            # value-weighted satisfaction
            reward += self._value[z.id] * ky * s.stress_coefficient  

        self._reserve.step(rain, et0, allocated)
        self._day += 1

        terminated = self._day >= self._season
        obs = self._obs(et0, rain) if not terminated else self._obs(0.0, 0.0)

        return obs, float(reward), terminated, False, {}
