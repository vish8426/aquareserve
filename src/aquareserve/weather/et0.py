"""FAO-56 Penman-Monteith reference evapotranspiration (ET0).

Implements the standardised daily grass reference ET0 from FAO Irrigation and Drainage Paper 56 (Allen et al., 1998), Chapter 4, Equation 6:

    ET0 = [0.408 Δ (Rn - G) + γ (900/(T+273)) u2 (es - ea)] / [Δ + γ (1 + 0.34 u2)]

All helper equations (saturation vapour pressure, slope Δ, psychrometric constant γ, extraterrestrial radiation Ra, clear-sky radiation Rso, net radiation Rn) follow the same reference.
Units are SI as used in FAO-56 (MJ, m, °C, kPa, m/s).

The module is validated against the FAO-56 worked example for Brussels (Uccle), 6 July - see ``tests/test_et0.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Physical constants (FAO-56)
# MJ m-2 min-1
SOLAR_CONSTANT = 0.0820  

# MJ K-4 m-2 day-1
STEFAN_BOLTZMANN = 4.903e-9  
ALBEDO_GRASS = 0.23

# 1/λ, converts MJ m-2 day-1 to mm day-1
LATENT_HEAT_FACTOR = 0.408  


def saturation_vapour_pressure(temp_c: float) -> float:
    """Saturation vapour pressure e°(T) [kPa] for air temperature T [°C] (FAO-56 eq. 11)."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def slope_saturation_vapour_pressure(temp_c: float) -> float:
    """Slope Δ of the saturation vapour pressure curve [kPa/°C] (FAO-56 eq. 13)."""
    es = saturation_vapour_pressure(temp_c)

    return 4098.0 * es / (temp_c + 237.3) ** 2


def atmospheric_pressure(elevation_m: float) -> float:
    """Atmospheric pressure P [kPa] at elevation z [m] (FAO-56 eq. 7)."""
    return 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26


def psychrometric_constant(elevation_m: float) -> float:
    """Psychrometric constant γ [kPa/°C] (FAO-56 eq. 8)."""
    return 0.000665 * atmospheric_pressure(elevation_m)


def extraterrestrial_radiation(latitude_deg: float, doy: int) -> float:
    """Daily extraterrestrial radiation Ra [MJ m-2 day-1] (FAO-56 eq. 21)."""
    phi = math.radians(latitude_deg)

    # inverse relative distance
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi / 365.0 * doy)  

    # solar declination
    decl = 0.409 * math.sin(2.0 * math.pi / 365.0 * doy - 1.39)  

    # sunset hour angle; clamp argument for polar day/night robustness
    x = -math.tan(phi) * math.tan(decl)
    x = max(-1.0, min(1.0, x))
    ws = math.acos(x)
    ra = (
        24.0 * 60.0 / math.pi
        * SOLAR_CONSTANT
        * dr
        * (ws * math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.sin(ws))
    )

    return max(0.0, ra)


def clear_sky_radiation(ra: float, elevation_m: float) -> float:
    """Clear-sky solar radiation Rso [MJ m-2 day-1] (FAO-56 eq. 37)."""
    return (0.75 + 2e-5 * elevation_m) * ra


def net_radiation(
    rs_mj: float,
    tmax_c: float,
    tmin_c: float,
    ea_kpa: float,
    ra: float,
    elevation_m: float,
) -> float:
    """Net radiation Rn [MJ m-2 day-1] from solar radiation Rs (FAO-56 eqs. 38-40)."""
    rns = (1.0 - ALBEDO_GRASS) * rs_mj  # net shortwave
    rso = clear_sky_radiation(ra, elevation_m)
    cloud = 1.35 * (rs_mj / rso) - 0.35 if rso > 0 else 0.0

    # FAO-56 caps the relative shortwave term
    cloud = max(0.05, min(1.0, cloud))  
    tmax_k = tmax_c + 273.16
    tmin_k = tmin_c + 273.16
    
    # net longwave
    rnl = (
        STEFAN_BOLTZMANN
        * ((tmax_k**4 + tmin_k**4) / 2.0)
        * (0.34 - 0.14 * math.sqrt(max(0.0, ea_kpa)))
        * cloud
    )  

    return rns - rnl


@dataclass(frozen=True)
class DailyWeather:
    """Inputs for a single day's ET0 computation."""

    tmax_c: float
    tmin_c: float

    # actual vapour pressure
    ea_kpa: float 

    # wind speed at 2 m 
    u2_ms: float  

    # incoming solar radiation
    rs_mj: float  
    latitude_deg: float
    elevation_m: float

    # day of year (1-366)
    doy: int  


def et0_penman_monteith(w: DailyWeather, soil_heat_flux: float = 0.0) -> float:
    """FAO-56 Penman-Monteith daily reference ET0 [mm/day].

    ``soil_heat_flux`` (G) is ~0 for daily time steps (FAO-56 eq. 42).
    """
    tmean = (w.tmax_c + w.tmin_c) / 2.0
    delta = slope_saturation_vapour_pressure(tmean)
    gamma = psychrometric_constant(w.elevation_m)

    es = (saturation_vapour_pressure(w.tmax_c) + saturation_vapour_pressure(w.tmin_c)) / 2.0
    vpd = max(0.0, es - w.ea_kpa)

    ra = extraterrestrial_radiation(w.latitude_deg, w.doy)
    rn = net_radiation(w.rs_mj, w.tmax_c, w.tmin_c, w.ea_kpa, ra, w.elevation_m)

    numerator = (
        LATENT_HEAT_FACTOR * delta * (rn - soil_heat_flux)
        + gamma * (900.0 / (tmean + 273.0)) * w.u2_ms * vpd
    )
    
    denominator = delta + gamma * (1.0 + 0.34 * w.u2_ms)

    return max(0.0, numerator / denominator)
