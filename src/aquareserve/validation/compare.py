"""Run our engine over a season and quantify agreement with a reference model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config.schema import CropModel, Zone
from ..models import CropCurve, SoilWaterBalance, taw_from_soil
from ..weather import columns as C


def run_aquareserve_season(zone: Zone, crop: CropModel, season: pd.DataFrame) -> pd.DataFrame:
    """Run the rainfed AquaReserve water balance over a season DataFrame.

    Returns per-day potential ET (etc_mm), actual ET (eta_mm), root-zone depletion (dr_mm) and stress coefficient (ks), indexed by date.
    """
    curve = CropCurve(crop)
    taw = taw_from_soil(zone.soil.total_available_water_mm_per_m, crop.root_depth.max_m)
    swb = SoilWaterBalance(taw, crop.depletion_fraction_p, zone.soil.initial_depletion_fraction * taw)
    rows = []

    for day, (date, r) in enumerate(season.iterrows()):
        etc = curve.crop_demand_mm(day, r[C.ET0])
        step = swb.step(rain_mm=r[C.RAIN], crop_et_mm=etc, irrigation_mm=0.0)

        rows.append(
            {
                "date": date,
                "etc_mm": etc,
                "eta_mm": step.actual_et_mm,
                "dr_mm": step.depletion_mm,
                "ks": step.stress_coefficient,
            }
        )

    return pd.DataFrame(rows).set_index("date")


@dataclass
class AgreementMetrics:
    """Agreement between our engine and a reference (aligned per day)."""

    # our ETc vs reference potential ETc (Kc*ET0)
    potential_etc_pct_diff: float 

    # our actual ET vs reference actual ET 
    eta_seasonal_pct_diff: float  
    dr_rmse_mm: float
    dr_corr: float
    ks_corr: float
    eta_corr: float

    def as_dict(self) -> dict[str, float]:
        return {k: round(float(v), 4) for k, v in self.__dict__.items()}


def _pct(a: float, b: float) -> float:
    return 100.0 * (a - b) / b if b else float("nan")


def _corr(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)

    if a.std() == 0 or b.std() == 0:
        return float("nan")

    return float(np.corrcoef(a, b)[0, 1])


def agreement(ours: pd.DataFrame, ref: pd.DataFrame) -> AgreementMetrics:
    """Compare our per-day output with a reference frame.

    ``ref`` must provide columns: ``etcm_mm`` (potential single-Kc crop ET), ``eta_mm`` (actual ET), ``dr_mm`` (root-zone depletion) and ``ks``.
    Rows are aligned by position (both cover the same season in order).
    """
    o = ours.reset_index(drop=True)
    r = ref.reset_index(drop=True)
    n = min(len(o), len(r))
    o, r = o.iloc[:n], r.iloc[:n]
    
    return AgreementMetrics(
        potential_etc_pct_diff=_pct(o["etc_mm"].sum(), r["etcm_mm"].sum()),
        eta_seasonal_pct_diff=_pct(o["eta_mm"].sum(), r["eta_mm"].sum()),
        dr_rmse_mm=float(np.sqrt(np.mean((o["dr_mm"].to_numpy() - r["dr_mm"].to_numpy()) ** 2))),
        dr_corr=_corr(o["dr_mm"], r["dr_mm"]),
        ks_corr=_corr(o["ks"], r["ks"]),
        eta_corr=_corr(o["eta_mm"], r["eta_mm"]),
    )
