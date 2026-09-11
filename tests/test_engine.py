"""Tests for the closed-loop simulation engine (multi-zone + shared reserve)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.controllers import RainfedController, ThresholdController
from aquareserve.simulation import SimulationEngine
from aquareserve.weather import read_silo_fao56

CONFIG = Path(__file__).parents[1] / "config" / "farm.example.yaml"
REAL_2000 = Path(__file__).parent / "fixtures" / "silo_mildura_2000.txt"


@pytest.fixture
def engine():
    sc = load_scenario(CONFIG)
    wx = read_silo_fao56(REAL_2000)

    return SimulationEngine(sc, wx, planting_date="2000-05-01"), sc


def test_rainfed_uses_no_reserve(engine):
    eng, _ = engine
    r = eng.run(RainfedController())

    assert r.irrigation_m3() == 0.0
    assert (r.reserve["withdrawal_m3"] == 0.0).all()


def test_reserve_stays_within_bounds(engine):
    eng, sc = engine
    r = eng.run(ThresholdController())

    assert (r.reserve["volume_m3"] >= -1e-6).all()
    assert (r.reserve["volume_m3"] <= sc.farm.reserve.capacity_m3 + 1e-6).all()


def test_irrigation_raises_yield(engine):
    eng, _ = engine
    rainfed = eng.run(RainfedController())
    irrigated = eng.run(ThresholdController())
    rain_prod = sum(y.actual_yield_t_ha for y in rainfed.yields.values())
    irr_prod = sum(y.actual_yield_t_ha for y in irrigated.yields.values())

    assert irrigated.irrigation_m3() > 0.0

    # spending the reserve must help
    assert irr_prod > rain_prod  


def test_withdrawals_bounded_by_reserve(engine):
    eng, sc = engine
    r = eng.run(ThresholdController())
    total_withdrawn = r.reserve["withdrawal_m3"].sum()
    total_inflow = r.reserve["capture_m3"].sum() + r.reserve["baseflow_m3"].sum()

    assert total_withdrawn <= sc.farm.reserve.initial_volume_m3 + total_inflow + 1e-6


def test_run_is_deterministic(engine):
    eng, _ = engine
    a = eng.run(ThresholdController())
    b = eng.run(ThresholdController())
    
    assert a.zone_days["irrig_m3"].sum() == pytest.approx(b.zone_days["irrig_m3"].sum())
