"""Deterministic synthetic daily weather generator.

Purpose: Give the simulation and the CI test-suite realistic, *reproducible* weather without network access to SILO/BoM.
The generator produces a plausible southern-hemisphere, winter-dominant-rainfall climate (like the Victorian Mallee) and computes FAO-56 ET0 for each day using the same equations as the real loader.

It is intentionally simple (seasonal sinusoids + stochastic rainfall), not a climate model, its job is to exercise the pipeline deterministically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import columns as C
from .et0 import (
    DailyWeather,
    clear_sky_radiation,
    et0_penman_monteith,
    extraterrestrial_radiation,
    saturation_vapour_pressure,
)


def generate_weather(
    start: str,
    end: str,
    latitude_deg: float,
    elevation_m: float,
    seed: int = 0,
) -> pd.DataFrame:
    """Generate a deterministic daily weather series in the canonical schema.

    Parameters
    ----------
    start, end      :   ISO date strings (inclusive range).
    latitude_deg    :   negative in the southern hemisphere.
    elevation_m     :   site elevation.
    seed            :   RNG seed - same seed + inputs => identical series.
    """
    dates = pd.date_range(start=start, end=end, freq="D")
    rng = np.random.default_rng(seed)
    n = len(dates)

    doy = dates.dayofyear.to_numpy()

    # Southern-hemisphere phase: warmest near 1 Jan (doy~1), coldest near July.
    seasonal = np.cos(2.0 * np.pi * (doy - 15) / 365.25)

    # --- Temperature (deg C) ---------------------------------------------
    tmean = 17.0 + 9.0 * seasonal + rng.normal(0.0, 1.5, n)
    diurnal = 11.0 + 2.0 * np.clip(seasonal, 0, None) + rng.normal(0.0, 1.0, n)
    diurnal = np.clip(diurnal, 4.0, None)
    tmax = tmean + diurnal / 2.0
    tmin = tmean - diurnal / 2.0

    # --- Rainfall (mm) - winter-dominant occurrence + gamma amounts ------
    # Tuned to a drought-prone semi-arid annual total (~300-350 mm/yr).
    p_wet = np.clip(0.18 - 0.10 * seasonal, 0.04, 0.5)
    wet = rng.random(n) < p_wet
    amounts = rng.gamma(shape=0.8, scale=6.0, size=n)
    rain = np.where(wet, amounts, 0.0)

    # --- Solar radiation Rs (MJ/m2/day) ----------------------------------
    ra = np.array([extraterrestrial_radiation(latitude_deg, int(d)) for d in doy])
    rso = np.array([clear_sky_radiation(r, elevation_m) for r in ra])
    clear_frac = np.clip(0.72 - 0.25 * wet + rng.normal(0.0, 0.05, n), 0.25, 0.8)
    rs = np.clip(rso * clear_frac, 0.5, None)

    # --- Wind (m/s) ------------------------------------------------------
    u2 = np.clip(rng.gamma(shape=4.0, scale=0.5, size=n), 0.5, None)

    # --- Actual vapour pressure ea (kPa) ---------------------------------
    es_tmin = np.array([saturation_vapour_pressure(t) for t in tmin])
    rh_factor = np.clip(0.65 + 0.2 * wet + rng.normal(0.0, 0.05, n), 0.4, 1.0)
    ea = es_tmin * rh_factor

    # --- ET0 per day -----------------------------------------------------
    et0 = np.empty(n)

    for i in range(n):
        et0[i] = et0_penman_monteith(
            DailyWeather(
                tmax_c=float(tmax[i]),
                tmin_c=float(tmin[i]),
                ea_kpa=float(ea[i]),
                u2_ms=float(u2[i]),
                rs_mj=float(rs[i]),
                latitude_deg=latitude_deg,
                elevation_m=elevation_m,
                doy=int(doy[i]),
            )
        )

    return pd.DataFrame(
        {
            C.TMAX: tmax,
            C.TMIN: tmin,
            C.TMEAN: tmean,
            C.RAIN: rain,
            C.RS: rs,
            C.U2: u2,
            C.EA: ea,
            C.ET0: et0,
        },
        
        index=pd.Index(dates, name=C.DATE),
    )
