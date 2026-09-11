"""Tests for the root-zone soil water balance (bounds, stress, mass conservation)."""

from __future__ import annotations

import pytest

from aquareserve.models.soil_water import SoilWaterBalance, taw_from_soil


def test_taw_from_soil():
    assert taw_from_soil(170.0, 1.5) == pytest.approx(255.0)


def test_rejects_bad_parameters():
    with pytest.raises(ValueError):
        SoilWaterBalance(taw_mm=0.0, depletion_fraction_p=0.5)

    with pytest.raises(ValueError):
        SoilWaterBalance(taw_mm=100.0, depletion_fraction_p=1.5)


def test_stress_coefficient_piecewise():
    # RAW = 50
    swb = SoilWaterBalance(taw_mm=100.0, depletion_fraction_p=0.5)  

    # below RAW: no stress
    assert swb.stress_coefficient(40.0) == 1.0          

    # at RAW boundary
    assert swb.stress_coefficient(50.0) == 1.0          

    # halfway RAW->TAW
    assert swb.stress_coefficient(75.0) == pytest.approx(0.5)  

    # at wilting
    assert swb.stress_coefficient(100.0) == pytest.approx(0.0)  


def test_dry_day_increases_depletion_by_etc_when_unstressed():
    swb = SoilWaterBalance(taw_mm=200.0, depletion_fraction_p=0.5)
    step = swb.step(rain_mm=0.0, crop_et_mm=6.0)

    assert step.stress_coefficient == 1.0
    assert step.actual_et_mm == pytest.approx(6.0)
    assert step.depletion_mm == pytest.approx(6.0)


def test_depletion_never_leaves_bounds():
    swb = SoilWaterBalance(taw_mm=100.0, depletion_fraction_p=0.5, initial_depletion_mm=90.0)

    # Many dry days: Dr approaches TAW asymptotically (Ks -> 0 as Dr -> TAW), never exceeding it.
    for _ in range(50):
        step = swb.step(rain_mm=0.0, crop_et_mm=10.0)

        assert 0.0 <= step.depletion_mm <= swb.taw

    assert 99.9 < swb.dr <= 100.0


def test_large_rain_refills_and_drains():
    swb = SoilWaterBalance(taw_mm=100.0, depletion_fraction_p=0.5, initial_depletion_mm=40.0)
    step = swb.step(rain_mm=200.0, crop_et_mm=5.0)

    # Profile refills to field capacity (Dr -> 0) and excess leaves as drainage.
    assert step.depletion_mm == pytest.approx(0.0)
    assert step.drainage_mm > 0.0


def test_mass_is_conserved_over_a_sequence():
    import random

    rng = random.Random(0)
    swb = SoilWaterBalance(taw_mm=150.0, depletion_fraction_p=0.55, initial_depletion_mm=30.0)
    dr0 = swb.dr
    water_in_total = et_total = drain_total = 0.0

    for _ in range(200):
        rain = rng.choice([0.0, 0.0, 5.0, 20.0])
        irr = rng.choice([0.0, 0.0, 10.0])
        etc = rng.uniform(2.0, 7.0)
        step = swb.step(rain_mm=rain, crop_et_mm=etc, irrigation_mm=irr)
        water_in_total += rain + irr
        et_total += step.actual_et_mm
        drain_total += step.drainage_mm

    # Dr_final - Dr_initial == -water_in + ET_actual + drainage
    lhs = swb.dr - dr0
    rhs = -water_in_total + et_total + drain_total
    
    assert lhs == pytest.approx(rhs, abs=1e-6)
