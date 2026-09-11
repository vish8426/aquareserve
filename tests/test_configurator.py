"""Tests for the configurator MVP."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import aquareserve.configurator.core as core  # noqa: E402
from aquareserve.configurator import (  # noqa: E402
    FarmProfile,
    ZoneInput,
    annual_recurring,
    build_scenario,
    configure,
    load_bom,
    size_hardware,
)

MODEL_ZONES = [ZoneInput("onion", 4, "drip"), ZoneInput("wheat", 12), ZoneInput("barley", 8)]


def test_bom_capex_reconciles_to_model():
    bom = load_bom(REPO_ROOT / "config" / "bom.yaml")

    # 3 zones, 20 ML new build, existing pump: matches the modeled ~126k capex
    items, capex = size_hardware(bom, zones=3, reserve_ml=20, build_storage=True, has_pump=True)

    assert capex == pytest.approx(126000.0)
    assert annual_recurring(bom) == pytest.approx(2700.0)

    # per-zone kit sums to 4000
    per_zone = sum(c["unit_cost"] for c in bom["per_zone_kit"])

    assert per_zone == pytest.approx(4000.0)


def test_no_pump_adds_pump_line():
    bom = load_bom(REPO_ROOT / "config" / "bom.yaml")

    _, with_pump = size_hardware(bom, 3, 20, True, has_pump=False)
    _, without = size_hardware(bom, 3, 20, True, has_pump=True)

    assert with_pump - without == pytest.approx(bom["optional_pump"]["unit_cost"])


def test_build_scenario_sets_zones_and_reserve():
    prof = FarmProfile(zones=[ZoneInput("onion", 4, "drip"), ZoneInput("wheat", 10)])
    sc = build_scenario(prof, 15)

    assert len(sc.farm.zones) == 2
    assert sc.farm.reserve.capacity_m3 == pytest.approx(15000.0)
    assert {z.crop for z in sc.farm.zones} == {"onion", "wheat"}


def test_unsupported_crop_raises():
    with pytest.raises(ValueError, match="Unsupported crop"):
        build_scenario(FarmProfile(zones=[ZoneInput("dragonfruit", 2)]), 20)


def test_configure_existing_reserve_no_storage():
    # existing dam -> fast path (no sizing sweep), storage capex excluded
    prof = FarmProfile(zones=MODEL_ZONES, existing_reserve_ml=20, has_pump=True)
    r = configure(prof)

    assert r["design"]["build_storage"] is False
    assert r["design"]["reserve_ml"] == 20
    assert r["design"]["capex_aud"] == pytest.approx(26000.0)  # no storage build
    assert r["economics"]["payback_years"] and r["economics"]["payback_years"] > 0
    assert r["economics"]["npv_aud"] > 0

    # the system protects the crop under drought
    assert r["outcome"]["production_t"] > r["outcome"]["rainfed_t"]
    assert r["outcome"]["yield_protected_pct"] > 0

    # onion (drip horticulture) is marketable
    onion = r["outcome"]["crops"]["onion"]

    assert onion["horticulture"] and onion["marketable"]


def test_recommend_maximises_npv(monkeypatch):
    # keep the test quick
    monkeypatch.setattr(core, "SIZING_CANDIDATES_ML", [10, 20])
    r = configure(FarmProfile(zones=MODEL_ZONES, has_pump=True))

    assert r["design"]["reserve_ml"] in (10, 20)

    sweep = r["design"]["reserve_sweep"]

    assert sweep is not None

    best = max(sweep.values(), key=lambda v: v["npv_aud"])

    assert r["economics"]["npv_aud"] == pytest.approx(best["npv_aud"])


def test_licence_cap_binds_and_reports_forgone(monkeypatch):
    # a licence below the NPV-optimal size hard-caps the recommendation
    monkeypatch.setattr(core, "SIZING_CANDIDATES_ML", [20])
    r = configure(FarmProfile(zones=MODEL_ZONES, has_pump=True, licence_cap_ml=10))

    assert r["design"]["licence_capped"] is True
    assert r["design"]["reserve_ml"] == 10
    assert r["design"]["licence_cap_ml"] == 10

    lic = r["licence"]

    assert lic["capped"] is True and lic["cap_ml"] == 10
    assert lic["uncapped_reserve_ml"] == 20

    # holding water back never protects more yield, so the forgone tonnage is non-negative
    assert lic["forgone_production_t"] >= 0

    # the sweep marks sizes above the licence
    assert r["design"]["reserve_sweep"][20]["over_licence"] is True


def test_licence_cap_not_binding_when_high(monkeypatch):
    monkeypatch.setattr(core, "SIZING_CANDIDATES_ML", [20])
    r = configure(FarmProfile(zones=MODEL_ZONES, has_pump=True, licence_cap_ml=100))

    assert r["design"]["licence_capped"] is False
    assert r["design"]["reserve_ml"] == 20


def test_licence_note_when_existing_reserve_exceeds_licence():
    # fast path (existing reserve): a licence below the existing reserve is flagged, not capped
    prof = FarmProfile(zones=MODEL_ZONES, existing_reserve_ml=20, has_pump=True, licence_cap_ml=15)
    r = configure(prof)

    assert r["design"]["licence_capped"] is False
    assert r["licence"]["cap_ml"] == 15
    assert r["licence"]["note"] and "exceeds" in r["licence"]["note"]
