"""Tests for the cost/ROI model."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config import load_scenario
from aquareserve.config.loader import load_economics
from aquareserve.metrics import (
    annual_benefit,
    dam_capacity_to_match,
    evaluate,
    npv,
    production_value,
    system_capex,
)
from aquareserve.metrics.agronomic import FarmMetrics, ZoneMetrics

CONFIG = Path(__file__).parents[1] / "config" / "farm.example.yaml"
ECON = Path(__file__).parents[1] / "config" / "economics.example.yaml"


@pytest.fixture
def sc():
    return load_scenario(CONFIG)


@pytest.fixture
def econ():
    return load_economics(ECON)


def _metrics(controller, prod):
    """A FarmMetrics with production split across the three zones (crop-keyed)."""
    zones = [
        ZoneMetrics("onion-1", "onion", 4.0, 0.9, prod["onion"] / 4.0, prod["onion"], 0, 0, 0, None),
        ZoneMetrics("wheat-1", "wheat", 12.0, 0.6, prod["wheat"] / 12.0, prod["wheat"], 0, 0, 0, None),
        ZoneMetrics("barley-1", "barley", 8.0, 0.7, prod["barley"] / 8.0, prod["barley"], 0, 0, 0, None),
    ]

    return FarmMetrics(controller=controller, zones=zones, total_production_t=sum(prod.values()), total_irrigation_m3=0.0)


def test_system_capex(sc, econ):
    # 20ML * 5/m3 + 3 zones * 4000 + 6000 gateway + 8000 install = 126,000
    assert system_capex(sc, econ) == pytest.approx(126_000.0)


def test_production_value(sc):
    m = _metrics("x", {"onion": 200.0, "wheat": 36.0, "barley": 24.0})

    # 200*450 + 36*320 + 24*300 = 90,000 + 11,520 + 7,200 = 108,720
    assert production_value(m, sc) == pytest.approx(108_720.0)


def test_annual_benefit_nets_opex_and_subscription(sc, econ):
    ctrl = _metrics("c", {"onion": 200.0, "wheat": 36.0, "barley": 24.0})
    rainfed = _metrics("rainfed", {"onion": 50.0, "wheat": 24.0, "barley": 16.0})
    uplift = production_value(ctrl, sc) - production_value(rainfed, sc)
    expected = uplift - econ.costs.annual_opex - econ.costs.subscription_per_year

    assert annual_benefit(ctrl, rainfed, sc, econ) == pytest.approx(expected)


def test_npv_formula():
    # capex 1000, annual 200, r=0.1, 2yrs
    got = npv(1000.0, 200.0, type("E", (), {"discount_rate": 0.1, "horizon_years": 2})())

    assert got == pytest.approx(-1000 + 200 / 1.1 + 200 / 1.21)


def test_evaluate_payback_and_no_benefit(sc, econ):
    ctrl = _metrics("c", {"onion": 200.0, "wheat": 36.0, "barley": 24.0})
    rainfed = _metrics("rainfed", {"onion": 50.0, "wheat": 24.0, "barley": 16.0})
    r = evaluate(ctrl, rainfed, ctrl, rainfed, sc, econ)

    assert r.payback_years == pytest.approx(r.capex / r.expected_annual_benefit)
    
    # If the controller does no better than rainfed, it never pays back.
    flat = evaluate(rainfed, rainfed, rainfed, rainfed, sc, econ)

    assert flat.payback_years is None


def test_dam_capacity_to_match_interpolates():
    prod = {20.0: 100.0, 30.0: 150.0, 40.0: 180.0}

    assert dam_capacity_to_match(150.0, prod) == pytest.approx(30.0)

    # halfway 30->40
    assert dam_capacity_to_match(165.0, prod) == pytest.approx(35.0)  

    # first size clears it
    assert dam_capacity_to_match(90.0, prod) == pytest.approx(20.0)   

    # unreachable
    assert dam_capacity_to_match(999.0, prod) is None                 
