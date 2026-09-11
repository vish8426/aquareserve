"""Tests for the RL comparison policy, CEM trainer and Gymnasium env."""

import numpy as np
import pytest

from aquareserve.config import load_scenario
from aquareserve.metrics import compute_metrics

from aquareserve.rl import (
    LinearPolicyController,
    cem_train,
    evaluate_weights,
    production_value,
)

from aquareserve.rl.base_features import N_FEATURES
from aquareserve.simulation import SimulationEngine
from aquareserve.weather import load_weather

CFG = "config/farm.example.yaml"


def _sc():
    return load_scenario(CFG)


def _wx(scen="severe"):
    return load_weather(_sc().climate, scenario_name=scen, base_dir=".")


def test_weights_shape_validation():
    sc = _sc()

    with pytest.raises(ValueError):
        LinearPolicyController(sc, np.zeros(N_FEATURES + 1))


def test_pretrained_loads_and_runs_as_controller():
    sc = _sc()
    rl = LinearPolicyController.pretrained(sc)

    assert rl.get_weights().shape == (N_FEATURES,)

    m = compute_metrics(SimulationEngine(sc, _wx(), planting_date="2000-05-01").run(rl), sc)

    assert 0.0 < m.total_production_t < 1000.0


def test_request_within_rate_limit_and_deterministic():
    sc = _sc()
    rl = LinearPolicyController.pretrained(sc)
    eng = SimulationEngine(sc, _wx(), planting_date="2000-05-01")
    a = compute_metrics(eng.run(rl), sc).total_production_t
    b = compute_metrics(eng.run(rl), sc).total_production_t

    assert a == pytest.approx(b)

    irrig = eng.run(rl).zone_days["irrig_mm"]

    assert (irrig >= -1e-9).all()


def test_pretrained_beats_rainfed_under_drought():
    sc = _sc()
    wx = _wx("severe")
    eng = SimulationEngine(sc, wx, planting_date="2000-05-01")

    from aquareserve.controllers import RainfedController

    rl = compute_metrics(eng.run(LinearPolicyController.pretrained(sc)), sc).total_production_t
    rainfed = compute_metrics(eng.run(RainfedController()), sc).total_production_t

    assert rl > rainfed


def test_production_value_positive():
    sc = _sc()
    eng = SimulationEngine(sc, _wx(), planting_date="2000-05-01")
    m = compute_metrics(eng.run(LinearPolicyController.pretrained(sc)), sc)

    assert production_value(m, sc) > 0.0


def test_cem_improves_over_zero_policy():
    sc = _sc()
    wx = [_wx("severe")]
    base = evaluate_weights(np.zeros(N_FEATURES), sc, wx, "2000-05-01")
    res = cem_train(sc, wx, iterations=3, population=8, seed=0)
    trained = evaluate_weights(res.weights, sc, wx, "2000-05-01")

    assert res.weights.shape == (N_FEATURES,)
    assert trained >= base


def test_env_reset_step_and_episode_length():
    pytest.importorskip("gymnasium")

    from aquareserve.rl.env import ReserveIrrigationEnv

    sc = _sc()
    env = ReserveIrrigationEnv(sc, _wx("severe"))
    obs, info = env.reset(seed=0)

    assert obs.shape == env.observation_space.shape

    steps, done = 0, False

    while not done:
        obs, r, done, trunc, info = env.step(np.full(env.nz, 0.4, dtype=np.float32))

        assert np.isfinite(r)

        steps += 1
        
    assert steps == env._season
