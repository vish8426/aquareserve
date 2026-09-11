"""Tests for unit conversions - the place irrigation models most often go wrong."""

from __future__ import annotations

import pytest

from aquareserve.units import (
    M3_PER_MM_HA,
    m3_to_ml,
    m3_to_mm,
    ml_to_m3,
    mm_to_m3,
)


def test_one_mm_over_one_ha_is_ten_m3():
    assert mm_to_m3(1.0, 1.0) == 10.0
    assert M3_PER_MM_HA == 10.0


def test_mm_to_m3_scales_with_area_and_depth():

    # 25 mm over 12 ha = 25 * 12 * 10 = 3000 m3
    assert mm_to_m3(25.0, 12.0) == 3000.0


def test_mm_m3_round_trip():
    depth, area = 18.5, 8.0
    volume = mm_to_m3(depth, area)
    
    assert m3_to_mm(volume, area) == pytest.approx(depth)


def test_m3_to_mm_rejects_nonpositive_area():
    with pytest.raises(ValueError):
        m3_to_mm(100.0, 0.0)


def test_megalitre_conversions():
    assert ml_to_m3(1.0) == 1000.0
    assert m3_to_ml(20000.0) == 20.0
    assert m3_to_ml(ml_to_m3(3.5)) == pytest.approx(3.5)
