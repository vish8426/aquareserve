"""Crop yield response to water deficit (FAO-33).

FAO Irrigation and Drainage Paper 33 relates a relative yield loss to a relative evapotranspiration deficit through the yield response factor Ky:

    (1 - Ya/Ym) = Ky * (1 - ETa/ETm)

where Ya/Ym is actual/maximum yield and ETa/ETm is actual/potential (crop) ET.

Two aggregation methods are provided:

* Seasonal - one Ky applied to the whole-season ET deficit.

Simple and robust.

* Stage-multiplicative - a per-stage Ky applied to each growth stage's deficit, then multiplied together:

    Ya/Ym = product over stages of [1 - Ky_stage * (1 - ETa_stage/ETm_stage)]

    This captures the fact that a deficit at a sensitive stage (wheat anthesis, onion bulb formation) costs far more yield than the same deficit at a tolerant stage. 
    It is the method the smart controllers will exploit.

Both clamp relative yield to [0, 1].
Absolute yield is the relative yield times the crop's reference (well-watered) yield.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.schema import CropModel, GrowthStage


@dataclass
class StageWater:
    """Accumulated potential and actual crop ET for one growth stage [mm]."""

    # potential crop ET (ET_m)
    etc_mm: float = 0.0

    # actual crop ET (ET_a)  
    eta_mm: float = 0.0  

    @property
    def relative_et(self) -> float:
        """ETa/ETm for the stage; 1.0 when there is no demand (no stress)."""
        if self.etc_mm <= 0.0:
            return 1.0

        return min(1.0, self.eta_mm / self.etc_mm)

    @property
    def relative_deficit(self) -> float:
        """1 - ETa/ETm, clamped to [0, 1]."""
        return max(0.0, min(1.0, 1.0 - self.relative_et))


@dataclass
class YieldResult:
    """Outcome of a season's yield calculation."""

    # stage-multiplicative Ya/Ym in [0, 1]
    relative_yield: float  

    # seasonal-method Ya/Ym in [0, 1]
    relative_yield_seasonal: float  

    # relative_yield * reference yield
    actual_yield_t_ha: float  
    reference_yield_t_ha: float
    per_stage: dict[GrowthStage, StageWater] = field(default_factory=dict)


class YieldAccumulator:
    """Accumulate daily ET over a season and compute FAO-33 yield response."""

    def __init__(self, crop: CropModel):
        self.crop = crop
        self._stages: dict[GrowthStage, StageWater] = {s: StageWater() for s in GrowthStage}

    def add_day(self, stage: GrowthStage, etc_mm: float, eta_mm: float) -> None:
        """Record one day's potential (ET_c) and actual (ET_a) crop ET for a stage."""
        sw = self._stages[stage]
        sw.etc_mm += max(0.0, etc_mm)
        sw.eta_mm += max(0.0, eta_mm)

    def _ky_for(self, stage: GrowthStage) -> float:
        """Per-stage Ky, falling back to the seasonal value if a stage is unset."""
        return self.crop.yield_response.by_stage.get(stage, self.crop.yield_response.seasonal)

    def relative_yield_stagewise(self) -> float:
        ratio = 1.0

        for stage, sw in self._stages.items():

            if sw.etc_mm <= 0.0:
                # stage never occurred / no demand -> no contribution
                continue  

            factor = 1.0 - self._ky_for(stage) * sw.relative_deficit
            ratio *= max(0.0, factor)

        return max(0.0, min(1.0, ratio))

    def relative_yield_seasonal(self) -> float:
        etc = sum(sw.etc_mm for sw in self._stages.values())
        eta = sum(sw.eta_mm for sw in self._stages.values())

        if etc <= 0.0:
            return 1.0

        deficit = max(0.0, min(1.0, 1.0 - eta / etc))
        rel = 1.0 - self.crop.yield_response.seasonal * deficit

        return max(0.0, min(1.0, rel))

    def result(self) -> YieldResult:
        rel = self.relative_yield_stagewise()
        
        return YieldResult(
            relative_yield=rel,
            relative_yield_seasonal=self.relative_yield_seasonal(),
            actual_yield_t_ha=rel * self.crop.reference_yield_t_per_ha,
            reference_yield_t_ha=self.crop.reference_yield_t_per_ha,
            per_stage={s: sw for s, sw in self._stages.items() if sw.etc_mm > 0.0},
        )
