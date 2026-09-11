"""Adapter to run the peer reviewed pyfao56 model on an AquaReserve scenario.

pyfao56 (Thorp, 2022) implements the FAO-56 dual crop coefficient soil-water balance.
We drive it with the SAME SILO ET0 our engine uses (MorP='M', measured reference ET) so the comparison isolates the soil-water and crop-stress logic rather than re-testing ET0 (which is validated separately against the FAO-56 Brussels worked example).

pyfao56 is an optional dependency (install via ``pip install '.[validation]'``).
"""

from __future__ import annotations

import math

import pandas as pd

from ..config.schema import CropModel, Zone
from ..weather import columns as C


def _dewpoint_c(ea_kpa: float) -> float:
    """Dewpoint temperature [C] from actual vapour pressure [kPa]."""
    x = math.log(max(ea_kpa, 1e-6) / 0.6108)

    return 237.3 * x / (17.27 - x)


def run_pyfao56_season(
    zone: Zone,
    crop: CropModel,
    season: pd.DataFrame,
    latitude_deg: float = -34.24,
    elevation_m: float = 50.0,
) -> pd.DataFrame:
    """Run pyfao56 over the season and return a per-day reference DataFrame.

    Columns: ``etcm_mm`` (potential single-Kc crop ET), ``eta_mm`` (actual ET), ``dr_mm`` (root-zone depletion), ``ks``, ``t_mm`` (transpiration), ``e_mm`` (soil evaporation), indexed by date.
    """
    try:
        from pyfao56 import Model, Parameters, Weather

    # pragma: no cover - exercised only without the extra dependency installed
    except ImportError as exc:  
        raise ImportError(
            "pyfao56 is required for validation; install with: pip install '.[validation]'"

        ) from exc

    wth = Weather()
    wth.z = elevation_m
    wth.lat = latitude_deg
    wth.wndht = 2.0
    wth.rfcrp = "S"

    idx = [f"{d.year}-{d.dayofyear:03d}" for d in season.index]

    wdata = []

    for _, r in season.iterrows():
        ea = r[C.EA]

        wdata.append(
            [r[C.RS], r[C.TMAX], r[C.TMIN], ea, _dewpoint_c(ea),
             float("nan"), float("nan"), 2.0, r[C.RAIN], r[C.ET0], "M"]
        )

    wth.wdata = pd.DataFrame(wdata, index=idx, columns=wth.cnames)

    par = Parameters()
    par.Kcmini, par.Kcmmid, par.Kcmend = crop.kc.initial, crop.kc.mid, crop.kc.end
    par.Kcbini, par.Kcbmid, par.Kcbend = crop.kc.initial, crop.kc.mid, crop.kc.end
    par.Lini = crop.stage_days.initial
    par.Ldev = crop.stage_days.development
    par.Lmid = crop.stage_days.mid
    par.Lend = crop.stage_days.late
    par.hini, par.hmax = 0.1, 1.0
    par.thetaFC = zone.soil.field_capacity
    par.thetaWP = zone.soil.wilting_point
    par.theta0 = zone.soil.field_capacity - zone.soil.initial_depletion_fraction * (zone.soil.field_capacity - zone.soil.wilting_point)
    par.Zrini, par.Zrmax = crop.root_depth.initial_m, crop.root_depth.max_m
    par.pbase = crop.depletion_fraction_p

    model = Model(idx[0], idx[-1], par, wth)
    model.run()

    o = model.odata.reset_index(drop=True)

    out = pd.DataFrame(
        {
            "etcm_mm": o["ETcm"].to_numpy(),
            "eta_mm": o["ETa"].to_numpy(),
            "dr_mm": o["Dr"].to_numpy(),
            "ks": o["Ks"].to_numpy(),
            "t_mm": o["T"].to_numpy(),
            "e_mm": o["E"].to_numpy(),
        },
        index=season.index[: len(o)],
    )
    
    return out
