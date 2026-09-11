"""Tests for the receding horizon MPC controller."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.config.schema import GrowthStage, ReserveStrategy
from aquareserve.controllers import MPCController, RainfedController, ThresholdController
from aquareserve.controllers.base import ZoneControlContext
from aquareserve.metrics import compute_metrics
from aquareserve.simulation import SimulationEngine
from aquareserve.weather import read_silo_fao56

CONFIG = Path(__file__).parents[1] / "config" / "farm.example.yaml"
REAL_2000 = Path(__file__).parent / "fixtures" / "silo_mildura_2000.txt"


@pytest.fixture
def setup():
    sc = load_scenario(CONFIG)
    wx = read_silo_fao56(REAL_2000)

    return sc, SimulationEngine(sc, wx, planting_date="2000-05-01")


def test_validates_horizon():
    sc = load_scenario(CONFIG)

    with pytest.raises(ValueError):
        MPCController(sc, horizon=1)


def test_mpc_irrigates_and_stays_within_reserve(setup):
    sc, eng = setup
    r = eng.run(MPCController(sc, horizon=21))

    assert r.irrigation_m3() > 0.0
    assert (r.reserve["volume_m3"] >= -1e-6).all()
    assert (r.reserve["volume_m3"] <= sc.farm.reserve.capacity_m3 + 1e-6).all()


def test_mpc_beats_rainfed_and_threshold(setup):
    sc, eng = setup
    rainfed = compute_metrics(eng.run(RainfedController()), sc).total_production_t
    threshold = compute_metrics(eng.run(ThresholdController()), sc).total_production_t
    mpc = compute_metrics(eng.run(MPCController(sc, horizon=21)), sc).total_production_t

    assert mpc > rainfed

    # planning ahead matches or beats the naive rule
    assert mpc >= threshold  


def test_mpc_request_defaults_to_zero_before_planning():
    sc = load_scenario(CONFIG)
    mpc = MPCController(sc, horizon=10)
    ctx = ZoneControlContext(
        zone_id="wheat-1", day_in_season=0, stage=GrowthStage.MID, depletion_mm=50.0,
        raw_mm=40.0, taw_mm=100.0, et0_mm=5.0, crop_et_mm=5.0, days_since_irrigation=9,
        max_application_rate_mm_per_day=20.0, strategy=ReserveStrategy.CRITICAL_STAGE_DEFICIT,
        stage_ky=1.0,
    )

    # nothing planned yet
    assert mpc.request_mm(ctx) == 0.0  


def test_mpc_rainfed_zone_gets_no_water():
    sc = load_scenario(CONFIG)
    mpc = MPCController(sc, horizon=14)
    
    # Only zones with a non-rainfed strategy are planned; a rainfed context returns 0.
    mpc.plan_day(0, {z.id: 30.0 for z in sc.farm.zones}, reserve_available_m3=5000.0, et0_today=6.0)

    ctx = ZoneControlContext(
        zone_id="does-not-exist", day_in_season=0, stage=GrowthStage.MID, depletion_mm=50.0,
        raw_mm=40.0, taw_mm=100.0, et0_mm=5.0, crop_et_mm=5.0, days_since_irrigation=9,
        max_application_rate_mm_per_day=20.0,
    )
    
    assert mpc.request_mm(ctx) == 0.0
