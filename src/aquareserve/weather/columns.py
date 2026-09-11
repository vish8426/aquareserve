"""Canonical column names for the weather DataFrame.

Every weather source (synthetic, SILO/BoM CSV) is normalised to these columns so downstream models never depend on a particular provider's naming.
"""

from __future__ import annotations

DATE = "date"
TMAX = "tmax_c"
TMIN = "tmin_c"
TMEAN = "tmean_c"
RAIN = "rain_mm"

# incoming solar radiation, MJ/m2/day
RS = "rs_mj"  

# wind speed at 2 m
U2 = "u2_ms"  

# actual vapour pressure
EA = "ea_kpa"  

# FAO-56 reference ET, mm/day
ET0 = "et0_mm"  

# Order used when materialising the DataFrame
ALL_COLUMNS = [TMAX, TMIN, TMEAN, RAIN, RS, U2, EA, ET0]
