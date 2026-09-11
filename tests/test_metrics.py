"""Tests for the agronomic + water metrics harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.controllers import RainfedController, ThresholdController
from aquareserve.metrics import compute_metrics
from aquareserve.simulation import SimulationEngine
from aquareserve.weather import read_silo_fao56

CONFIG = Path(__file__).parents[1] / "config" / "farm.example.yaml"
REAL_2000 = Path(__file__).parent / "fixtures" / "silo_mildura_2000.txt"


@pytest.fixture
def engine():
    sc = load_scenario(CONFIG)
    wx = read_silo_fao56(REAL_2000)

    return SimulationEngine(sc, wx, planting_date="2000-05-01"), sc


def test_rainfed_metrics(engine):
    eng, sc = engine
    m = compute_metrics(eng.run(RainfedController()), sc)

    assert m.total_irrigation_m3 == 0.0

    for z in m.zones:
        assert z.irrigation_mm == 0.0

        # undefined without irrigation
        assert z.wue_kg_per_m3 is None  
        assert z.production_t == pytest.approx(z.yield_t_ha * z.area_ha)


def test_irrigated_metrics_have_wue(engine):
    eng, sc = engine
    m = compute_metrics(eng.run(ThresholdController()), sc)

    assert m.total_irrigation_m3 > 0.0
    assert m.total_production_t > 0.0
    assert 0 <= m.reserve_survival_days <= len(eng.weather)

    for z in m.zones:
        if z.irrigation_m3 > 0:
            assert z.wue_kg_per_m3 is not None and z.wue_kg_per_m3 > 0


def test_irrigation_beats_rainfed_on_production(engine):
    eng, sc = engine
    rainfed = compute_metrics(eng.run(RainfedController()), sc)
    irrigated = compute_metrics(eng.run(ThresholdController()), sc)
    
    assert irrigated.total_production_t > rainfed.total_production_t
