"""Validate the AquaReserve engine against pyfao56 on real Mildura seasons.

Runs each crop's rainfed season through our engine and through pyfao56 (driven by the same SILO ET0), prints agreement metrics, and writes a committed reference fixture so CI can check agreement without the optional pyfao56 dependency.

Usage:
    pip install '.[validation,viz]'
    python scripts/validate_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.validation import agreement, run_aquareserve_season  
from aquareserve.validation.pyfao56_ref import run_pyfao56_season  
from aquareserve.weather import load_weather  

PLANTING = "2000-05-01"
FIXTURE_OUT = REPO_ROOT / "tests" / "fixtures" / "pyfao56_wheat2000_reference.csv"


def season_for(zone, crop, weather):
    start = pd.Timestamp(PLANTING)

    return weather.loc[start : start + pd.Timedelta(days=crop.stage_days.total - 1)]


def main() -> int:
    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    weather = load_weather(sc.climate, base_dir=str(REPO_ROOT))

    print("AquaReserve engine validation vs pyfao56 (real Mildura 2000 seasons)")
    print(f"{'crop':8s} {'pot.ETc %':>9s} {'ETa %':>7s} {'Dr RMSE':>8s} "
          f"{'Dr corr':>8s} {'Ks corr':>8s} {'ETa corr':>9s}")

    for zone in sc.farm.zones:
        crop = sc.crops[zone.crop]
        season = season_for(zone, crop, weather)
        ours = run_aquareserve_season(zone, crop, season)
        ref = run_pyfao56_season(zone, crop, season,
                                 latitude_deg=sc.farm.location.latitude,
                                 elevation_m=sc.farm.location.elevation_m)

        m = agreement(ours, ref)
        
        print(f"{crop.name:8s} {m.potential_etc_pct_diff:+8.1f}% {m.eta_seasonal_pct_diff:+6.1f}% "
              f"{m.dr_rmse_mm:7.1f}  {m.dr_corr:8.3f} {m.ks_corr:8.3f} {m.eta_corr:9.3f}")

        if zone.crop == "wheat":
            ref.to_csv(FIXTURE_OUT)

    print(f"\nWrote reference fixture: {FIXTURE_OUT.relative_to(REPO_ROOT)}")
    print("Note: potential ETc (Kc*ET0) should match ~0%. Actual-ET magnitude differs")
    print("because pyfao56 partitions transpiration + soil evaporation (dual Kc) while")
    print("our control-oriented engine uses a single lumped bucket; trends still track.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
