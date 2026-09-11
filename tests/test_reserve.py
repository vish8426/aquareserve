"""Tests for the finite reserve dynamics model."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.config.schema import Reserve, ReserveSource
from aquareserve.models import ReserveModel


@pytest.fixture
def reserve(example_farm_path: Path):
    return load_scenario(example_farm_path).farm.reserve


def test_starts_at_configured_volume(reserve):
    r = ReserveModel(reserve)

    assert r.volume == pytest.approx(reserve.initial_volume_m3)
    assert r.fraction_full == pytest.approx(reserve.initial_volume_m3 / reserve.capacity_m3)


def test_initial_volume_capped_at_capacity():
    r = ReserveModel(Reserve(capacity_m3=1000.0, initial_volume_m3=1000.0))

    assert r.volume == 1000.0


def test_rain_capture_formula(reserve):
    r = ReserveModel(reserve)

    # 30 mm over 6000 m2 catchment at 0.8 runoff = 30 * 6000 * 0.8 * 0.001 = 144 m3
    assert r.capture_from_rain(30.0) == pytest.approx(144.0)
    assert r.capture_from_rain(0.0) == 0.0


def test_baseflow_from_bore(reserve):
    r = ReserveModel(reserve)

    assert r.baseflow() == pytest.approx(50.0)


def test_open_water_evaporation(reserve):
    r = ReserveModel(reserve)

    # pan_coefficient 0.7 * (ET0 8 / 0.7) = 8 mm; over 4000 m2 = 32 m3
    assert r.open_water_evaporation(8.0) == pytest.approx(32.0)


def test_never_goes_negative():
    r = ReserveModel(Reserve(capacity_m3=1000.0, initial_volume_m3=40.0, surface_area_m2=1000.0))
    step = r.step(rain_mm=0.0, et0_mm=6.0, withdrawal_request_m3=10_000.0)

    assert step.volume_m3 >= 0.0
    assert step.withdrawal_m3 <= 40.0 + step.baseflow_m3


def test_capacity_spill():
    src = [ReserveSource(type="rain", catchment_area_m2=1_000_000.0, runoff_coefficient=1.0)]
    r = ReserveModel(Reserve(capacity_m3=1000.0, initial_volume_m3=900.0, sources=src))

    # capture 50 * 1e6 * 1 * 0.001 = 50000 m3
    step = r.step(rain_mm=50.0, et0_mm=0.0)  

    assert step.volume_m3 == pytest.approx(1000.0)  # capped
    assert step.spill_m3 > 0.0


def test_evaporation_bounded_by_available_water():
    r = ReserveModel(Reserve(capacity_m3=1000.0, initial_volume_m3=5.0, surface_area_m2=1_000_000.0))

    # would-be evap enormous
    step = r.step(rain_mm=0.0, et0_mm=10.0)  

    assert step.evaporation_m3 <= 5.0 + step.baseflow_m3
    assert step.volume_m3 >= 0.0


def test_mass_is_conserved_over_a_sequence(reserve):
    rng = random.Random(0)
    r = ReserveModel(reserve)
    v0 = r.volume
    cap = base = evap = wd = spill = 0.0

    for _ in range(400):
        step = r.step(
            rain_mm=rng.choice([0.0, 0.0, 5.0, 40.0]),
            et0_mm=rng.uniform(1.0, 9.0),
            withdrawal_request_m3=rng.choice([0.0, 100.0, 500.0]),
        )

        cap += step.capture_m3
        base += step.baseflow_m3
        evap += step.evaporation_m3
        wd += step.withdrawal_m3
        spill += step.spill_m3
        
    # V_final - V_initial == inflow - outflow
    assert r.volume - v0 == pytest.approx(cap + base - evap - wd - spill, abs=1e-6)
