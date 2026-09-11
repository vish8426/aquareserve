"""Cross-Entropy Method policy search for the RL comparison policy.

The RL agent is a linear policy (rl.policy.LinearPolicyController) whose weights are found by the Cross-Entropy Method, a standard derivative-free reinforcement learning / policy- search algorithm: sample a population of weight vectors from a Gaussian, evaluate each by running the real simulation engine (so the training return is exactly the deployment objective), keep the top "elite" fraction and refit the Gaussian to the elites.
Repeating this concentrates the distribution on high-return policies.

CEM is chosen over deep RL (PPO/SAC) as the in-repo, CI-safe method: it is pure NumPy, has no heavy learned-gradient dependency (torch), trains in seconds and is fully reproducible from a seed (ADR-012).
An optional Stable-Baselines3 PPO path over the same Gymnasium env (rl.env) is provided separately for the deep-RL comparison.

Return signal: Total farmgate production value (sum over zones of yield x area x price), averaged over the supplied training weathers so the policy generalises across drought severity rather than overfitting one season.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config.schema import Scenario
from ..metrics import compute_metrics
from ..simulation import SimulationEngine
from .base_features import N_FEATURES
from .policy import LinearPolicyController


def production_value(metrics, scenario: Scenario) -> float:
    """Total farmgate value (AUD) of a run's production across all zones."""
    total = 0.0

    for z in metrics.zones:
        zone = next(zz for zz in scenario.farm.zones if zz.id == z.zone_id)
        total += z.production_t * scenario.crops[zone.crop].price_per_t

    return total


@dataclass
class CEMResult:
    weights: np.ndarray
    best_return: float
    history: list[float] = field(default_factory=list)


def evaluate_weights(weights: np.ndarray, scenario: Scenario, weathers: list[pd.DataFrame], planting: str) -> float:
    """Mean production value of the policy across the training weathers."""
    ctrl = LinearPolicyController(scenario, weights)
    vals = []

    for wx in weathers:
        eng = SimulationEngine(scenario, wx, planting_date=planting)
        vals.append(production_value(compute_metrics(eng.run(ctrl), scenario), scenario))

    return float(np.mean(vals))


def _score_baselines(scenario: Scenario, weathers: list[pd.DataFrame], planting: str) -> list[tuple[float, float]]:
    """Per-weather (floor, span) = (rainfed value, oracle - rainfed) for normalisation.

    Normalising each weather to its own controllable range gives a normal year and a drought year equal weight in training, so the policy is not swamped by the higher absolute value of the wetter season.
    """
    from ..controllers import OracleController, RainfedController

    out = []

    for wx in weathers:
        eng = SimulationEngine(scenario, wx, planting_date=planting)
        floor = production_value(compute_metrics(eng.run(RainfedController()), scenario), scenario)

        ceil = production_value(
            compute_metrics(eng.run(OracleController(scenario, wx, planting)), scenario), scenario
        )

        out.append((floor, max(ceil - floor, 1.0)))

    return out


def cem_train(scenario: Scenario, weathers: list[pd.DataFrame], planting: str = "2000-05-01", iterations: int = 12, population: int = 24, elite_frac: float = 0.25, init_std: float = 1.0, seed: int = 0) -> CEMResult:
    """Search policy weights by the Cross-Entropy Method on the real engine."""
    rng = np.random.default_rng(seed)
    mean = np.zeros(N_FEATURES)
    std = np.full(N_FEATURES, init_std)
    n_elite = max(2, int(population * elite_frac))
    best_w, best_r, history = mean.copy(), -np.inf, []
    bases = _score_baselines(scenario, weathers, planting)

    def norm_return(w: np.ndarray) -> float:
        ctrl = LinearPolicyController(scenario, w)
        scores = []

        for wx, (floor, span) in zip(weathers, bases, strict=True):
            eng = SimulationEngine(scenario, wx, planting_date=planting)
            val = production_value(compute_metrics(eng.run(ctrl), scenario), scenario)
            scores.append((val - floor) / span)

        return float(np.mean(scores))

    for _ in range(iterations):
        pop = rng.normal(mean, std, size=(population, N_FEATURES))
        returns = np.array([norm_return(w) for w in pop])
        elite_idx = returns.argsort()[-n_elite:]
        elite = pop[elite_idx]
        mean, std = elite.mean(axis=0), elite.std(axis=0) + 1e-6
        it_best = returns.max()

        if it_best > best_r: 
            best_r, best_w = float(it_best), pop[returns.argmax()].copy()
            
        history.append(best_r)

    return CEMResult(weights=best_w, best_return=best_r, history=history)
