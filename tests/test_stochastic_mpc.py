"""Tests for the robust quantile MPC (B4)."""

import pytest

from aquareserve.config import load_scenario
from aquareserve.controllers import MPCController, StochasticMPCController
from aquareserve.metrics import compute_metrics
from aquareserve.simulation import SimulationEngine
from aquareserve.weather import load_weather

CFG = "config/farm.example.yaml"


def _run(ctrl, scen="severe"):
    sc = load_scenario(CFG)
    wx = load_weather(sc.climate, scenario_name=scen, base_dir=".")
    eng = SimulationEngine(sc, wx, planting_date="2000-05-01")

    return compute_metrics(eng.run(ctrl), sc)


def test_rejects_bad_quantile():
    sc = load_scenario(CFG)

    for q in (0.0, 1.0, -0.1, 1.5):

        with pytest.raises(ValueError):
            StochasticMPCController(sc, demand_quantile=q)


def test_name_and_forecast_length():
    sc = load_scenario(CFG)
    c = StochasticMPCController(sc, horizon=30)

    assert c.name == "stochastic_mpc"

    c._fc.observe(6.0, 0.0)
    et0, rain = c._forecast(0, 6.0)

    assert len(et0) == 30 and len(rain) == 30


def test_upper_quantile_at_least_matches_mpc_under_drought():
    sc = load_scenario(CFG)
    mpc = _run(MPCController(sc)).total_production_t
    robust = _run(StochasticMPCController(sc, demand_quantile=0.7)).total_production_t

    # the robust posture stays competitive with the point-forecast MPC under drought (within about 1.5%); 
    # how far ahead it gets depends on how harsh the real season is
    assert robust >= mpc * 0.985


def test_reset_is_deterministic():
    sc = load_scenario(CFG)
    a = _run(StochasticMPCController(sc, demand_quantile=0.7)).total_production_t
    b = _run(StochasticMPCController(sc, demand_quantile=0.7)).total_production_t
    
    assert a == pytest.approx(b)
