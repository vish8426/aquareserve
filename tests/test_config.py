"""Tests for the configuration schema and loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aquareserve.config import load_scenario
from aquareserve.config.loader import load_crop_models

from aquareserve.config.schema import (
    Reserve,
    ReserveStrategy,
    Scenario,
    SoilProfile,
    Zone,
)


# --------------------------------------------------------------------------- #
# Happy path: the example scenario loads and is internally consistent
# --------------------------------------------------------------------------- #
def test_example_scenario_loads(example_farm_path: Path):
    scenario = load_scenario(example_farm_path)

    assert isinstance(scenario, Scenario)


def test_example_scenario_totals(example_farm_path: Path):
    scenario = load_scenario(example_farm_path)

    assert scenario.total_area_ha == pytest.approx(24.0) 
    assert len(scenario.farm.zones) == 3


def test_reserve_reference_is_resolved(example_farm_path: Path):
    scenario = load_scenario(example_farm_path)

    assert scenario.farm.reserve is not None
    assert scenario.farm.reserve.capacity_m3 == pytest.approx(20000.0)
    assert scenario.farm.reserve.initial_volume_m3 <= scenario.farm.reserve.capacity_m3


def test_every_zone_has_a_crop_model(example_farm_path: Path):
    scenario = load_scenario(example_farm_path)

    for zone in scenario.farm.zones:
        assert zone.crop in scenario.crops


def test_crop_packs_have_expected_values(config_dir: Path):
    from aquareserve.config.schema import GrowthStage

    crops = load_crop_models(config_dir / "crops")

    assert set(crops) == {"wheat", "barley", "onion"}

    wheat = crops["wheat"]
    by_stage = wheat.yield_response.by_stage

    # Wheat anthesis (mid stage) must be the most yield sensitive stage.
    most_sensitive_stage = max(by_stage, key=lambda s: by_stage[s])

    assert most_sensitive_stage is GrowthStage.MID

    # Kc rises from emergence to mid-season canopy.
    assert wheat.kc.mid > wheat.kc.initial


def test_onion_is_shallow_rooted(config_dir: Path):
    crops = load_crop_models(config_dir / "crops")

    assert crops["onion"].root_depth.max_m <= 0.5


# --------------------------------------------------------------------------- #
# Validation guards: bad configs must fail loudly
# --------------------------------------------------------------------------- #
def test_soil_rejects_wilting_point_above_field_capacity():
    with pytest.raises(ValidationError):

        SoilProfile(
            field_capacity=0.20,

            # invalid: above field capacity
            wilting_point=0.25,  
            total_available_water_mm_per_m=150.0,
        )


def test_reserve_rejects_initial_above_capacity():
    with pytest.raises(ValidationError):
        Reserve(capacity_m3=10000.0, initial_volume_m3=12000.0)


def test_duplicate_zone_ids_rejected(tmp_path: Path, config_dir: Path):
    bad_farm = tmp_path / "farm.yaml"

    bad_farm.write_text(
        """
name: "Dup Zones"
location: {region: "X", latitude: -34.0, longitude: 142.0, elevation_m: 50}
reserve: {capacity_m3: 1000, initial_volume_m3: 500}
zones:
  - id: "z1"
    crop: "wheat"
    area_ha: 1.0
    irrigation_system: "drip"
    strategy: "rainfed"
    soil: {field_capacity: 0.3, wilting_point: 0.1, total_available_water_mm_per_m: 150}
  - id: "z1"
    crop: "wheat"
    area_ha: 1.0
    irrigation_system: "drip"
    strategy: "rainfed"
    soil: {field_capacity: 0.3, wilting_point: 0.1, total_available_water_mm_per_m: 150}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_scenario(bad_farm, climate_path=config_dir / "climate.example.yaml", crops_dir=config_dir / "crops")


def test_missing_crop_model_raises(tmp_path: Path, config_dir: Path):
    bad_farm = tmp_path / "farm.yaml"

    bad_farm.write_text(
        """
name: "Unknown Crop"
location: {region: "X", latitude: -34.0, longitude: 142.0, elevation_m: 50}
reserve: {capacity_m3: 1000, initial_volume_m3: 500}
zones:
  - id: "z1"
    crop: "sorghum"   # no crop pack exists for this
    area_ha: 1.0
    irrigation_system: "drip"
    strategy: "rainfed"
    soil: {field_capacity: 0.3, wilting_point: 0.1, total_available_water_mm_per_m: 150}
""",
        encoding="utf-8",
    )

    with pytest.raises((ValidationError, ValueError)):
        load_scenario(bad_farm, climate_path=config_dir / "climate.example.yaml", crops_dir=config_dir / "crops")


def test_zone_strategy_enum_round_trips():
    zone = Zone(
        id="z",
        crop="wheat",
        area_ha=5.0,
        irrigation_system="drip",
        strategy="critical_stage_deficit",
        soil=SoilProfile(
            field_capacity=0.3, wilting_point=0.1, total_available_water_mm_per_m=150.0
        ),
    )
    
    assert zone.strategy is ReserveStrategy.CRITICAL_STAGE_DEFICIT
