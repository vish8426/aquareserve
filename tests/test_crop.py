"""Tests for the FAO-56 crop coefficient curve, growth stage and root depth."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config.loader import load_crop_models
from aquareserve.config.schema import GrowthStage
from aquareserve.models.crop import CropCurve


@pytest.fixture
def wheat_curve(config_dir: Path) -> CropCurve:
    return CropCurve(load_crop_models(config_dir / "crops")["wheat"])


def test_kc_anchor_points(wheat_curve: CropCurve):
    kc = wheat_curve.crop.kc

    # start: Kc_ini
    assert wheat_curve.kc(0) == pytest.approx(kc.initial)          

    # into mid stage
    mid_day = wheat_curve._end_dev + 1                          

    assert wheat_curve.kc(mid_day) == pytest.approx(kc.mid)
    assert wheat_curve.kc(wheat_curve.total_days + 10) == pytest.approx(kc.end)


def test_kc_rises_monotonically_through_development(wheat_curve: CropCurve):
    start, end = wheat_curve._end_ini, wheat_curve._end_dev
    values = [wheat_curve.kc(d) for d in range(start, end + 1)]

    assert all(b >= a for a, b in zip(values, values[1:], strict=False))
    assert values[0] < values[-1]


def test_growth_stage_transitions(wheat_curve: CropCurve):
    assert wheat_curve.stage(0) is GrowthStage.INITIAL
    assert wheat_curve.stage(wheat_curve._end_ini) is GrowthStage.DEVELOPMENT
    assert wheat_curve.stage(wheat_curve._end_dev) is GrowthStage.MID
    assert wheat_curve.stage(wheat_curve._end_mid) is GrowthStage.LATE


def test_root_depth_grows_to_max(wheat_curve: CropCurve):
    rd = wheat_curve.crop.root_depth

    assert wheat_curve.root_depth_m(0) == pytest.approx(rd.initial_m)
    assert wheat_curve.root_depth_m(wheat_curve.total_days) == pytest.approx(rd.max_m)

    # Monotonic non-decreasing growth
    depths = [wheat_curve.root_depth_m(d) for d in range(0, wheat_curve.total_days, 5)]
    
    assert all(b >= a for a, b in zip(depths, depths[1:], strict=False))


def test_crop_demand(wheat_curve: CropCurve):
    # ET_c = Kc * ET0
    assert wheat_curve.crop_demand_mm(0, 5.0) == pytest.approx(wheat_curve.kc(0) * 5.0)
