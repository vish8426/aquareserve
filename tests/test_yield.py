"""Tests for the FAO-33 yield response model."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.config.loader import load_crop_models
from aquareserve.config.schema import GrowthStage
from aquareserve.models import YieldAccumulator


@pytest.fixture

def wheat(config_dir: Path):
    return load_crop_models(config_dir / "crops")["wheat"]


def _accumulate(crop, eta_by_stage: dict[GrowthStage, float], etc: float = 100.0):
    acc = YieldAccumulator(crop)

    for stage in GrowthStage:
        acc.add_day(stage, etc, eta_by_stage.get(stage, etc))

    return acc.result()


def test_full_water_gives_reference_yield(wheat):
    result = _accumulate(wheat, {})

    assert result.relative_yield == pytest.approx(1.0)
    assert result.relative_yield_seasonal == pytest.approx(1.0)
    assert result.actual_yield_t_ha == pytest.approx(wheat.reference_yield_t_per_ha)


def test_sensitive_stage_deficit_costs_more_than_tolerant(wheat):

    # Same 50% ET deficit at a sensitive (MID/anthesis) vs tolerant (INITIAL) stage.
    mid = _accumulate(wheat, {GrowthStage.MID: 50.0}).relative_yield
    ini = _accumulate(wheat, {GrowthStage.INITIAL: 50.0}).relative_yield

    assert mid < ini

    # Exact FAO-33 stage factors: 1 - Ky*deficit
    assert mid == pytest.approx(1.0 - wheat.yield_response.by_stage[GrowthStage.MID] * 0.5)
    assert ini == pytest.approx(1.0 - wheat.yield_response.by_stage[GrowthStage.INITIAL] * 0.5)


def test_yield_decreases_monotonically_with_deficit(wheat):
    prev = 1.0001

    for eta in [100.0, 80.0, 60.0, 40.0, 20.0, 0.0]:
        rel = _accumulate(wheat, {GrowthStage.MID: eta}).relative_yield

        assert rel <= prev
        
        prev = rel


def test_relative_yield_never_negative(wheat):

    # Total loss at the most sensitive stage must clamp at 0 - not go negative.
    rel = _accumulate(wheat, {GrowthStage.MID: 0.0}).relative_yield

    assert 0.0 <= rel <= 1.0


def test_zero_demand_is_safe_and_unstressed(wheat):

    # No crop demand at all -> no division by zero - full relative yield.
    acc = YieldAccumulator(wheat)

    for stage in GrowthStage:
        acc.add_day(stage, 0.0, 0.0)

    result = acc.result()

    assert result.relative_yield == pytest.approx(1.0)
    assert result.per_stage == {}


def test_seasonal_method_matches_formula(wheat):

    # Uniform 30% seasonal deficit -> 1 - Ky_seasonal * 0.3
    result = _accumulate(wheat, {s: 70.0 for s in GrowthStage})
    expected = 1.0 - wheat.yield_response.seasonal * 0.3

    assert result.relative_yield_seasonal == pytest.approx(expected)


def test_per_stage_only_includes_stages_with_demand(wheat):
    acc = YieldAccumulator(wheat)
    acc.add_day(GrowthStage.MID, 100.0, 60.0)
    
    result = acc.result()

    assert set(result.per_stage) == {GrowthStage.MID}
    assert result.per_stage[GrowthStage.MID].relative_deficit == pytest.approx(0.4)
