"""Engine validation against pyfao56.

The primary test is CI-safe: it runs OUR engine on the committed real 2000 SILO fixture and compares to a committed pyfao56 reference, so agreement is checked on every run without needing the optional pyfao56 dependency. 
A second test, skipped when pyfao56 is not installed, re-runs pyfao56 live to guard the reference itself.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aquareserve.config import load_scenario
from aquareserve.validation import agreement, run_aquareserve_season
from aquareserve.weather import read_silo_fao56

FIX = Path(__file__).parent / "fixtures"
REAL_2000 = FIX / "silo_mildura_2000.txt"
PYFAO56_REF = FIX / "pyfao56_wheat2000_reference.csv"
PLANTING = pd.Timestamp("2000-05-01")


def _wheat_season():
    sc = load_scenario(Path(__file__).parents[1] / "config" / "farm.example.yaml")
    zone = next(z for z in sc.farm.zones if z.id == "wheat-1")
    crop = sc.crops["wheat"]
    weather = read_silo_fao56(REAL_2000)
    season = weather.loc[PLANTING : PLANTING + pd.Timedelta(days=crop.stage_days.total - 1)]

    return zone, crop, season


def test_engine_matches_pyfao56_reference():
    """Our engine tracks the committed pyfao56 reference within documented bounds."""
    zone, crop, season = _wheat_season()
    ours = run_aquareserve_season(zone, crop, season)
    ref = pd.read_csv(PYFAO56_REF, index_col=0, parse_dates=True)
    m = agreement(ours, ref)

    # Potential crop ET (Kc*ET0) must match the reference almost exactly.
    assert abs(m.potential_etc_pct_diff) < 2.0

    # Daily dynamics must track strongly (trend), even though the actual-ET magnitude differs by the single- vs dual-Kc evaporation treatment.
    assert m.dr_corr > 0.85
    assert m.eta_corr > 0.85
    assert m.ks_corr > 0.6

    # The known magnitude offset should stay within a documented envelope.
    assert -50.0 < m.eta_seasonal_pct_diff < 0.0


def test_reference_fixture_is_wellformed():
    ref = pd.read_csv(PYFAO56_REF, index_col=0, parse_dates=True)

    assert {"etcm_mm", "eta_mm", "dr_mm", "ks"} <= set(ref.columns)

    # ~190-day wheat season
    assert len(ref) > 150  
    assert (ref["dr_mm"] >= 0).all()


@pytest.mark.skipif(
    __import__("importlib.util", fromlist=["find_spec"]).find_spec("pyfao56") is None,
    reason="pyfao56 not installed (optional validation dependency)",
)

def test_live_pyfao56_reproduces_reference():
    """Re-run pyfao56 and confirm the committed reference is still reproducible."""
    from aquareserve.validation.pyfao56_ref import run_pyfao56_season

    zone, crop, season = _wheat_season()
    live = run_pyfao56_season(zone, crop, season, latitude_deg=-34.24, elevation_m=50.0)
    ref = pd.read_csv(PYFAO56_REF, index_col=0, parse_dates=True)
    
    assert np.isclose(live["eta_mm"].sum(), ref["eta_mm"].sum(), rtol=0.01)
    assert np.isclose(live["dr_mm"].to_numpy(), ref["dr_mm"].to_numpy(), atol=1.0).mean() > 0.95
