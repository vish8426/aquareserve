"""Tests for the perfect foresight oracle controller."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.config.schema import GrowthStage
from aquareserve.controllers import MPCController, OracleController, RainfedController
from aquareserve.controllers.base import ZoneControlContext
from aquareserve.metrics import compute_metrics
from aquareserve.simulation import SimulationEngine
from aquareserve.weather import columns as C
from aquareserve.weather import read_silo_fao56

CONFIG = Path(__file__).parents[1] / "config" / "farm.example.yaml"
REAL_2000 = Path(__file__).parent / "fixtures" / "silo_mildura_2000.txt"


def _severe(wx):
    """Scale a real record into a severe-drought year (as drought injection does)."""
    out = wx.copy()
    out[C.RAIN] = out[C.RAIN] * 0.4
    out[C.ET0] = out[C.ET0] * 1.25

    return out


@pytest.fixture
def setup():
    sc = load_scenario(CONFIG)
    wx = read_silo_fao56(REAL_2000)

    return sc, wx


def test_oracle_irrigates_within_reserve(setup):
    sc, wx = setup
    eng = SimulationEngine(sc, wx, planting_date="2000-05-01")
    r = eng.run(OracleController(sc, wx, "2000-05-01", horizon=21))

    assert r.irrigation_m3() > 0.0
    assert (r.reserve["volume_m3"] >= -1e-6).all()
    assert (r.reserve["volume_m3"] <= sc.farm.reserve.capacity_m3 + 1e-6).all()


def test_oracle_beats_mpc_under_drought(setup):
    """Under scarcity, perfect foresight is a clear upper bound over the realistic MPC."""
    sc, wx = setup
    severe = _severe(wx)
    eng = SimulationEngine(sc, severe, planting_date="2000-05-01")
    mpc = compute_metrics(eng.run(MPCController(sc)), sc).total_production_t
    oracle = compute_metrics(eng.run(OracleController(sc, severe, "2000-05-01")), sc).total_production_t
    rainfed = compute_metrics(eng.run(RainfedController()), sc).total_production_t

    assert oracle >= rainfed

    # foresight is worth real yield when water is scarce
    assert oracle > mpc  


def test_oracle_request_out_of_range_is_zero(setup):
    sc, wx = setup
    oracle = OracleController(sc, wx, "2000-05-01", horizon=14)

    ctx = ZoneControlContext(
        zone_id="wheat-1", day_in_season=99999, stage=GrowthStage.MID, depletion_mm=50.0,
        raw_mm=40.0, taw_mm=100.0, et0_mm=5.0, crop_et_mm=5.0, days_since_irrigation=9,
        max_application_rate_mm_per_day=20.0,
    )
    
    assert oracle.request_mm(ctx) == 0.0
