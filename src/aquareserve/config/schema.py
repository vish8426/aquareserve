"""Declarative configuration schema for an AquaReserve simulation scenario.

The whole simulation is driven by validated configuration so that *no agronomic constant is hard-coded in the engine*.
A scenario is composed of four parts:

    farm      - zones (crop, area, irrigation system, soil, strategy) + reserve
    crops     - per-crop model packs (Kc curve, stage lengths, root depth, Ky)
    climate   - region, dataset reference, period, drought-injection scenarios
    reserve   - finite water store dynamics (sources, capacity, evaporation)

These map 1:1 onto the Pydantic models below.
The loader (`loader.py`) reads the YAML, resolves cross-references (e.g. each zone's crop -> a crop model pack) and returns a fully-validated :class:`Scenario`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class IrrigationSystem(str, Enum):
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    BROADACRE_SPRINKLER = "broadacre_sprinkler"
    CENTER_PIVOT = "center_pivot"
    FURROW = "furrow"


class ReserveStrategy(str, Enum):
    """High-level reserve-release policy for a zone (the controller refines it)."""

    RAINFED = "rainfed"
    NEAR_FULL_BACKUP = "near_full_backup"
    CRITICAL_STAGE_DEFICIT = "critical_stage_deficit"


class GrowthStage(str, Enum):
    INITIAL = "initial"
    DEVELOPMENT = "development"
    MID = "mid"
    LATE = "late"


class DatasetSource(str, Enum):
    SILO = "silo"
    BOM = "bom"
    CSV = "csv"
    SYNTHETIC = "synthetic"


# --------------------------------------------------------------------------- #
# Farm
# --------------------------------------------------------------------------- #
class Location(BaseModel):
    region: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    # Dead Sea ~ -430 m is the floor
    elevation_m: float = Field(0.0, ge=-430)  


class SoilProfile(BaseModel):
    """Root-zone soil water-holding properties.

    `total_available_water_mm_per_m` (TAW) is the plant-available water held between field capacity and wilting point, per metre of root depth.
    """
    name: str = "default_loam"
    field_capacity: float = Field(..., gt=0, lt=1, description="volumetric, m3/m3")
    wilting_point: float = Field(..., ge=0, lt=1, description="volumetric, m3/m3")
    total_available_water_mm_per_m: float = Field(..., gt=0)
    initial_depletion_fraction: float = Field(0.0, ge=0, le=1, description="fraction of TAW already depleted at season start")

    @model_validator(mode="after")

    def _check_water_points(self) -> SoilProfile:
        if self.wilting_point >= self.field_capacity:
            raise ValueError("wilting_point must be below field_capacity")

        return self


class Zone(BaseModel):
    """A single irrigation management unit (one crop, one block of land)."""
    id: str

    crop: str = Field(..., description="key into the crop model packs, e.g. 'wheat'")
    area_ha: float = Field(..., gt=0)
    irrigation_system: IrrigationSystem
    strategy: ReserveStrategy
    soil: SoilProfile
    planting_date: str | None = Field(None, description="ISO date 'YYYY-MM-DD'; if null, uses climate period start")
    irrigation_efficiency: float = Field(0.85, gt=0, le=1, description="fraction of applied water reaching the root zone")
    max_application_rate_mm_per_day: float = Field(25.0, gt=0)


class ReserveSource(BaseModel):
    type: str = Field(..., description="e.g. 'rainwater_harvest', 'farm_dam', 'bore'")
    initial_volume_m3: float = Field(0.0, ge=0)

    # Optional rainwater-harvest parameters
    catchment_area_m2: float | None = Field(None, ge=0)
    runoff_coefficient: float | None = Field(None, ge=0, le=1)

    # Optional steady inflow (e.g. bore allocation)
    daily_inflow_m3: float | None = Field(None, ge=0)


class Reserve(BaseModel):
    name: str = "farm_reserve"
    capacity_m3: float = Field(..., gt=0)
    initial_volume_m3: float = Field(..., ge=0)
    sources: list[ReserveSource] = Field(default_factory=list)

    # Open-water evaporation from the store surface
    surface_area_m2: float = Field(0.0, ge=0)
    pan_coefficient: float = Field(0.7, gt=0, le=1.5)

    @model_validator(mode="after")

    def _check_capacity(self) -> Reserve:
        if self.initial_volume_m3 > self.capacity_m3:
            raise ValueError("initial_volume_m3 cannot exceed capacity_m3")

        return self


class Farm(BaseModel):
    name: str
    location: Location
    zones: list[Zone] = Field(..., min_length=1)

    # Reserve may be inline or referenced from a separate file (resolved by loader)
    reserve: Reserve | None = None
    reserve_ref: str | None = Field(None, description="relative path to a reserve YAML")

    @model_validator(mode="after")

    def _unique_zone_ids(self) -> Farm:
        ids = [z.id for z in self.zones]

        if len(ids) != len(set(ids)):
            raise ValueError("zone ids must be unique")
            
        return self


# --------------------------------------------------------------------------- #
# Crop model pack
# --------------------------------------------------------------------------- #
class CropCoefficients(BaseModel):
    """FAO-56 single crop coefficient (Kc) at the three anchor points."""
    initial: float = Field(..., gt=0, le=1.5)
    mid: float = Field(..., gt=0, le=1.6)
    end: float = Field(..., gt=0, le=1.5)


class StageDays(BaseModel):
    """Length of each FAO-56 growth stage in days."""
    initial: int = Field(..., gt=0)
    development: int = Field(..., gt=0)
    mid: int = Field(..., gt=0)
    late: int = Field(..., gt=0)

    @property
    def total(self) -> int:
        return self.initial + self.development + self.mid + self.late


class RootDepth(BaseModel):
    initial_m: float = Field(..., gt=0)
    max_m: float = Field(..., gt=0)

    @model_validator(mode="after")

    def _check(self) -> RootDepth:
        if self.max_m < self.initial_m:
            raise ValueError("max_m must be >= initial_m")

        return self


class YieldResponse(BaseModel):
    """FAO-33 yield response factors (Ky).
    Higher Ky => more yield lost per unit of water deficit at that stage.
    The seasonal value applies to whole-season deficit; per-stage values capture sensitivity (e.g. anthesis for wheat).
    """
    seasonal: float = Field(..., gt=0)
    by_stage: dict[GrowthStage, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_stage_keys(self) -> YieldResponse:
        for k, v in self.by_stage.items():

            if v < 0:
                raise ValueError(f"Ky for stage {k} must be non-negative")

        return self


class CropModel(BaseModel):
    """A crop-agnostic parameter pack. Adding a crop = adding one of these."""
    name: str
    display_name: str
    kc: CropCoefficients
    stage_days: StageDays
    root_depth: RootDepth
    yield_response: YieldResponse
    depletion_fraction_p: float = Field(..., gt=0, lt=1, description="FAO-56 p: fraction of TAW depletable before stress")
    seasonal_water_need_mm: tuple[float, float] = Field(..., description="(low, high) reference seasonal requirement")
    reference_yield_t_per_ha: float = Field(..., gt=0)
    price_per_t: float = Field(100.0, gt=0, description="farmgate price per tonne")
    notes: str = ""

    @model_validator(mode="after")

    def _check_need_range(self) -> CropModel:
        lo, hi = self.seasonal_water_need_mm

        if lo <= 0 or hi < lo:
            raise ValueError("seasonal_water_need_mm must be (low>0, high>=low)")

        return self


# --------------------------------------------------------------------------- #
# Climate
# --------------------------------------------------------------------------- #
class ClimateDataset(BaseModel):
    source: DatasetSource
    station_or_grid: str = Field(..., description="station name or grid cell id")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    variables: list[str] = Field(default_factory=lambda: ["rain", "et0", "max_temp", "min_temp", "radiation"])
    path: str | None = Field(None, description="local path for CSV/cached data")


# ISO date
class ClimatePeriod(BaseModel):
    start: str  
    end: str  


class DroughtScenario(BaseModel):
    """A multiplier-based perturbation of the historical record.

    rainfall_multiplier < 1 scales daily rainfall down to emulate drought; et0_multiplier > 1 emulates the hotter/drier evaporative demand that typically accompanies it.
    """
    name: str

    year: int | None = Field(
        None,
        description="if set, use this real calendar year from the record (re-based onto "
        "the base-period year); multipliers below are only a fallback when that year is absent",
    )

    rainfall_multiplier: float = Field(1.0, ge=0)
    et0_multiplier: float = Field(1.0, gt=0)
    description: str = ""


class ClimateConfig(BaseModel):
    region: str
    dataset: ClimateDataset
    period: ClimatePeriod
    drought_scenarios: list[DroughtScenario] = Field(default_factory=list)

    @model_validator(mode="after")

    def _unique_scenario_names(self) -> ClimateConfig:
        names = [s.name for s in self.drought_scenarios]

        if len(names) != len(set(names)):
            raise ValueError("drought scenario names must be unique")

        return self


# --------------------------------------------------------------------------- #
# Assembled scenario (produced by the loader, not read directly from one file)
# --------------------------------------------------------------------------- #
class Scenario(BaseModel):
    """Fully-resolved, validated simulation scenario ready for the engine."""
    farm: Farm
    crops: dict[str, CropModel]
    climate: ClimateConfig

    @model_validator(mode="after")

    def _every_zone_crop_has_a_model(self) -> Scenario:
        missing = sorted({z.crop for z in self.farm.zones} - set(self.crops))

        if missing:
            raise ValueError(f"no crop model pack found for zone crop(s): {', '.join(missing)}")

        if self.farm.reserve is None:
            raise ValueError("farm.reserve must be resolved before building a Scenario")

        return self

    @property
    def total_area_ha(self) -> float:
        return sum(z.area_ha for z in self.farm.zones)


# --------------------------------------------------------------------------- #
# Economics (cost / ROI model)
# --------------------------------------------------------------------------- #
class SystemCosts(BaseModel):
    """Capital and operating costs of the AquaReserve hardware system."""
    storage_capex_per_m3: float = Field(..., gt=0, description="on-farm storage cost per m3")
    per_zone_hardware: float = Field(..., ge=0, description="sensors + valve + node per zone")
    gateway: float = Field(..., ge=0, description="LoRa gateway + edge controller + solar/battery")
    install: float = Field(..., ge=0, description="installation and commissioning")
    annual_opex: float = Field(..., ge=0, description="maintenance, comms, power per year")
    subscription_per_year: float = Field(..., ge=0, description="premium cloud features per year")


class EconomicsConfig(BaseModel):
    """Economic assumptions for the cost/ROI model."""
    currency: str = "AUD"
    water_value_per_ml: float = Field(0.0, ge=0, description="opportunity value of reserve water")
    discount_rate: float = Field(..., ge=0, lt=1)
    horizon_years: int = Field(..., gt=0)
    severe_year_probability: float = Field(0.2, ge=0, le=1)
    costs: SystemCosts
