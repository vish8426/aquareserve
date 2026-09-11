"""Tests for FAO-56 Penman-Monteith ET0, validated against the published example."""

from __future__ import annotations

import pytest

from aquareserve.weather.et0 import (
    DailyWeather,
    et0_penman_monteith,
    extraterrestrial_radiation,
    net_radiation,
    saturation_vapour_pressure,
)


def test_saturation_vapour_pressure_known_values():
    # FAO-56 Table: e0(20 C) ~ 2.338 kPa, e0(25 C) ~ 3.168 kPa
    assert saturation_vapour_pressure(20.0) == pytest.approx(2.338, abs=0.01)
    assert saturation_vapour_pressure(25.0) == pytest.approx(3.168, abs=0.01)


def test_fao56_brussels_worked_example():
    """FAO-56 worked example (Uccle, Brussels, 6 July): ET0 ~ 3.9 mm/day.

    Expected intermediate values from the reference: Ra ~ 41.09, Rn ~ 13.28.
    """
    lat, elev, doy = 50.80, 100.0, 187
    ra = extraterrestrial_radiation(lat, doy)
    rn = net_radiation(22.07, 21.5, 12.3, 1.409, ra, elev)
    et0 = et0_penman_monteith(
        DailyWeather(
            tmax_c=21.5, tmin_c=12.3, ea_kpa=1.409, u2_ms=2.078,
            rs_mj=22.07, latitude_deg=lat, elevation_m=elev, doy=doy,
        )
    )

    assert ra == pytest.approx(41.09, abs=0.1)
    assert rn == pytest.approx(13.28, abs=0.1)
    assert et0 == pytest.approx(3.9, abs=0.1)


def test_et0_is_nonnegative_and_increases_with_heat_and_radiation():
    base = DailyWeather(
        tmax_c=20.0, tmin_c=10.0, ea_kpa=1.2, u2_ms=2.0,
        rs_mj=18.0, latitude_deg=-34.0, elevation_m=50.0, doy=15,
    )

    hotter = DailyWeather(
        tmax_c=34.0, tmin_c=20.0, ea_kpa=1.2, u2_ms=2.0,
        rs_mj=28.0, latitude_deg=-34.0, elevation_m=50.0, doy=15,
    )

    et0_base = et0_penman_monteith(base)
    et0_hot = et0_penman_monteith(hotter)

    assert et0_base >= 0.0
    assert et0_hot > et0_base


def test_extraterrestrial_radiation_positive_and_seasonal():
    # Southern hemisphere summer (Jan) should exceed winter (Jul) at -34 deg.
    ra_summer = extraterrestrial_radiation(-34.0, 15)
    ra_winter = extraterrestrial_radiation(-34.0, 196)
    
    assert ra_summer > ra_winter > 0
