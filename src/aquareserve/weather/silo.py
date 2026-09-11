"""Parser for real SILO 'fao56' point (station) data files.

SILO (Queensland Government Long Paddock service) publishes free daily Australian climate data from 1889 to yesterday under CC BY 4.0.
The 'fao56' format is the Standard variable set plus FAO-56 Penman-Monteith short-crop reference ET (ET0), which is exactly what the engine needs.

File structure (see https://www.longpaddock.qld.gov.au/silo/about/file-formats-and-samples):
  * a descriptive header block whose lines start with a double quote or exclamation
  * a space-delimited data block whose lines start with a date in yyyymmdd form:

    Date  Day Date2  T.Max Smx T.Min Smn Rain Srn Evap Sev Radn Ssl VP Svp RHmaxT RHminT FAO56

We map the columns we use into the canonical weather schema.
Wind is not provided (SILO computes ET0 with a default 2 m/s), so u2 is set to that assumption; the soil-water balance consumes ET0 directly, so wind is not otherwise needed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from . import columns as C

# 0-based column indices within a whitespace-split fao56 data row.
_COL = {"date": 0, "tmax": 3, "tmin": 5, "rain": 7, "radn": 11, "vp": 13, "et0": 17}
_MIN_FIELDS = 18
_DATA_LINE = re.compile(r"^\d{8}\s")
_SILO_DEFAULT_WIND_MS = 2.0

# SILO sentinel values for missing data
_MISSING = {-99.9, 9999.9, 999.9}  


def read_silo_fao56(path: str | Path) -> pd.DataFrame:
    """Parse a SILO fao56 station file into the canonical weather DataFrame."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"SILO data file not found: {path}")

    records: list[dict] = []

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not _DATA_LINE.match(line):
            continue

        f = line.split()

        if len(f) < _MIN_FIELDS:

            # skip any truncated trailing line
            continue  

        try:
            date = pd.to_datetime(f[_COL["date"]], format="%Y%m%d")
            tmax = float(f[_COL["tmax"]])
            tmin = float(f[_COL["tmin"]])
            rain = float(f[_COL["rain"]])
            radn = float(f[_COL["radn"]])
            vp = float(f[_COL["vp"]])
            et0 = float(f[_COL["et0"]])

        except (ValueError, IndexError):
            continue

        if any(v in _MISSING for v in (tmax, tmin, rain, radn, vp, et0)):
            continue

        records.append(
            {
                C.DATE: date,
                C.TMAX: tmax,
                C.TMIN: tmin,
                C.TMEAN: (tmax + tmin) / 2.0,
                C.RAIN: rain,
                C.RS: radn,
                C.U2: _SILO_DEFAULT_WIND_MS,
                C.EA: vp / 10.0,  # hPa -> kPa
                C.ET0: et0,
            }
        )

    if not records:
        raise ValueError(f"no valid SILO data rows found in {path}")
        
    return pd.DataFrame(records).set_index(C.DATE).sort_index()
