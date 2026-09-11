"""Parametric linear policy expressed as a controller.

The reinforcement learning comparison policy is a small linear policy mapping a handful of per-zone features to an irrigation fraction of the zone's maximum application rate.
It is a normal ``Controller`` so it runs inside the *same* simulation engine as every other strategy - the RL agent is judged on exactly the objective the others are which keeps the comparison fair.

Reserve awareness comes through the ``plan_day`` hook (as the MPC does): 
    - Each day the policy caches the current reserve fraction so per-zone decisions back off as the shared reserve runs low.

Training (rl.cem) searches the weight vector; this module only defines the policy and its features so the learned weights is an inspectable artefact.
"""

from __future__ import annotations

import math

import numpy as np

from ..config.schema import Scenario
from ..models import ReserveModel
from ._pretrained import PRETRAINED_WEIGHTS

# re-exported for callers
from .base_features import N_FEATURES  

__all__ = ["LinearPolicyController", "N_FEATURES"]


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class LinearPolicyController:
    """Linear irrigation policy over per-zone features; a standard controller."""

    def __init__(self, scenario: Scenario, weights: np.ndarray | None = None):
        self.scenario = scenario
        self.name = "rl_policy"
        self.weights = (np.zeros(N_FEATURES) if weights is None else np.asarray(weights, dtype=float))

        if self.weights.shape != (N_FEATURES,):
            raise ValueError(f"weights must have shape ({N_FEATURES},)")

        # Per-zone economic value density, normalised to [0, 1] across zones.
        raw = {}

        for z in scenario.farm.zones:
            crop = scenario.crops[z.crop]
            raw[z.id] = crop.reference_yield_t_per_ha * crop.price_per_t

        vmax = max(raw.values()) or 1.0

        self._value_norm = {zid: v / vmax for zid, v in raw.items()}
        self._reserve_cap = ReserveModel(scenario.farm.reserve).capacity
        self._reserve_frac = 1.0

    def set_weights(self, weights: np.ndarray) -> None:
        self.weights = np.asarray(weights, dtype=float).reshape(N_FEATURES)

    def get_weights(self) -> np.ndarray:
        return self.weights.copy()

    @classmethod
    def pretrained(cls, scenario: Scenario) -> LinearPolicyController:
        """Policy loaded with the committed CEM-trained weights (rl._pretrained)."""
        return cls(scenario, np.array(PRETRAINED_WEIGHTS, dtype=float))

    def reset(self) -> None:
        self._reserve_frac = 1.0

    def plan_day(self, day_index: int, depletions: dict[str, float], reserve_available_m3: float, et0_today: float, rain_today: float = 0.0) -> None:
        cap = self._reserve_cap or 1.0
        self._reserve_frac = min(1.0, max(0.0, reserve_available_m3 / cap))

    def _features(self, ctx) -> np.ndarray:
        taw = ctx.taw_mm or 1.0
        depl = ctx.depletion_mm / taw
        stress = max(0.0, (ctx.depletion_mm - ctx.raw_mm) / taw)
        value = self._value_norm.get(ctx.zone_id, 0.5)
        res = self._reserve_frac

        return np.array([
            1.0,                                             # bias
            depl,                                            # depletion fraction
            stress,                                          # stress beyond RAW
            ctx.stage_ky,                                    # yield sensitivity now
            ctx.et0_mm / 8.0,                                # evaporative demand
            res,                                             # shared reserve remaining
            min(1.0, ctx.days_since_irrigation / 10.0),      # recency
            value,                                           # zone economic value
            depl * value,                                    # value-weighted need
            ctx.stage_ky * res,                              # protect critical stages if water spare
            stress * value,                                  # high-value stress interaction
        ])

    def request_mm(self, ctx) -> float:
        frac = _sigmoid(float(self.weights @ self._features(ctx)))

        return frac * ctx.max_application_rate_mm_per_day
