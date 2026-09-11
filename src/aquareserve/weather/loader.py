"""Load daily weather for a scenario, normalised to the canonical schema.

Resolution order:
  1. If the dataset source is 'silo' and the referenced file exists, parse the real SILO fao56 station file (rain, temps, radiation, vapour pressure, FAO-56 ET0).
  2. Else if a CSV path exists, read and normalise it.
  3. Otherwise generate a deterministic synthetic series (offline/CI fallback). 
Then, if a drought scenario name is given, apply its multipliers.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config.schema import ClimateConfig, DatasetSource
from . import columns as C
from .drought import apply_drought, find_scenario
from .silo import read_silo_fao56
from .synthetic import generate_weather

logger = logging.getLogger(__name__)

# Common source-column aliases mapped to canonical names (generic CSV inputs).
_ALIASES: dict[str, str] = {
    "date": C.DATE, "day": C.DATE,
    "max_temp": C.TMAX, "tmax": C.TMAX, "t.max": C.TMAX, "maxt": C.TMAX,
    "min_temp": C.TMIN, "tmin": C.TMIN, "t.min": C.TMIN, "mint": C.TMIN,
    "rain": C.RAIN, "rainfall": C.RAIN, "daily_rain": C.RAIN, "precip": C.RAIN,
    "radn": C.RS, "radiation": C.RS, "rs": C.RS, "solar": C.RS, "srad": C.RS,
    "wind": C.U2, "u2": C.U2, "windspeed": C.U2,
    "vp": C.EA, "ea": C.EA, "vapour_pressure": C.EA, "vapor_pressure": C.EA,
    "et0": C.ET0, "et_short": C.ET0, "eto": C.ET0, "fao56": C.ET0,
}


def _normalise_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known source columns to canonical names and index by date."""
    renamed = {c: _ALIASES.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns}
    df = df.rename(columns=renamed)

    if C.DATE not in df.columns:
        raise ValueError("weather CSV must contain a recognisable date column")

    df[C.DATE] = pd.to_datetime(df[C.DATE])
    df = df.set_index(C.DATE).sort_index()

    if C.TMEAN not in df.columns and {C.TMAX, C.TMIN} <= set(df.columns):
        df[C.TMEAN] = (df[C.TMAX] + df[C.TMIN]) / 2.0

    return df


def _resolve_path(ds_path: str | None, base_dir: str | Path | None) -> Path | None:
    if not ds_path:
        return None

    p = Path(ds_path)

    if base_dir and not p.is_absolute():
        p = Path(base_dir) / p

    return p


def load_weather(
    climate: ClimateConfig,
    scenario_name: str | None = None,
    base_dir: str | Path | None = None,
    seed: int = 0,
    elevation_m: float = 50.0,
) -> pd.DataFrame:
    """Return a daily weather DataFrame for the given climate config.

    Parameters
    ----------
    climate         : Validated climate configuration.
    scenario_name   : Optional drought scenario to apply (e.g. "severe").
    base_dir        : Directory to resolve a relative dataset path against.
    seed            : RNG seed for the synthetic fallback (reproducibility).
    elevation_m     : Site elevation for the synthetic ET0 computation.
    """
    ds = climate.dataset
    path = _resolve_path(ds.path, base_dir)
    have_file = path is not None and path.exists()

    if ds.source == DatasetSource.SILO and have_file:
        df = read_silo_fao56(path)

    elif ds.source in (DatasetSource.CSV, DatasetSource.BOM) and have_file:
        df = _normalise_csv(pd.read_csv(path))

    else:
        if ds.source != DatasetSource.SYNTHETIC:

            logger.warning(
                "weather source '%s' selected but data file %s not found; "
                "falling back to deterministic synthetic weather (seed=%d).",
                ds.source.value, path, seed,
            )

        df = generate_weather(
            start=climate.period.start,
            end=climate.period.end,
            latitude_deg=ds.latitude,
            elevation_m=elevation_m,
            seed=seed,
        )

    scenario = (
        find_scenario(climate.drought_scenarios, scenario_name)

        if scenario_name is not None else None
    )

    base_year = pd.Timestamp(climate.period.start).year

    # A scenario may pin a real calendar year (e.g. 2019 drought).
    # Extract that years real daily values and re-base them onto the base-period year so the season window and planting date stay identical across scenarios.
    # Otherwise trim to the period.
    used_year = False

    if scenario is not None and scenario.year is not None:
        dfy = df[df.index.year == scenario.year]

        if not dfy.empty:
            dfy = dfy.copy()
            dfy.index = pd.DatetimeIndex([ts.replace(year=base_year) for ts in dfy.index])
            df = dfy.sort_index()
            used_year = True

    if not used_year:
        df = df.loc[climate.period.start : climate.period.end]

    # Multipliers apply to synthetic/perturbed scenarios only; a real pinned year is used as is (applying multipliers on top would double count the drought).
    if scenario is not None and not used_year:
        df = apply_drought(df, scenario)

    return df
