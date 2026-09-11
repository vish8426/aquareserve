"""Smart rule-based critical-stage deficit controller.

The insight from the baseline comparison: a naive threshold rule spends the finite reserve indiscriminately and runs it dry mid-season, leaving the yield-critical stages unprotected.
This controller spends the same reserve more purposefully, guided by each zone's configured strategy and the FAO-33 stage sensitivity (Ky):

* rainfed zones -> never irrigate.
* near-full-backup zones -> keep well-watered (refill when readily-available water is used up). 
                            Justified for small, high-value, stress-intolerant horticulture (onion).

* critical-stage-deficit -> irrigate only when the crop is BOTH at a zones (broadacre cereals)  yield-sensitive stage (stage Ky >= critical_ky) AND actually short of water (depletion past RAW). 
                            Outside those windows it saves water for when a cubic metre protects the most yield.

Because the engine allocates the shared reserve in zone order (high-value zones first) and this rule withholds cereal water outside the sensitive stages, more of the reserve survives to the anthesis/grain-fill windows where it matters most.
"""

from __future__ import annotations

from ..config.schema import ReserveStrategy
from .base import ZoneControlContext


class SmartCriticalStageController:
    """Strategy-aware, stage-weighted deficit controller."""

    def __init__(self, critical_ky: float = 0.6):
        if not 0 < critical_ky < 2:
            raise ValueError("critical_ky must be in (0, 2)")
            
        self.critical_ky = critical_ky
        self.name = "smart_rule"

    def request_mm(self, ctx: ZoneControlContext) -> float:
        if ctx.strategy == ReserveStrategy.RAINFED:
            return 0.0

        if ctx.strategy == ReserveStrategy.NEAR_FULL_BACKUP:
            
            # Keep the profile topped up: refill to field capacity once the crop would begin to feel stress.
            return ctx.depletion_mm if ctx.depletion_mm >= ctx.raw_mm else 0.0

        # CRITICAL_STAGE_DEFICIT: only water sensitive stages that are short of water.
        if ctx.stage_ky >= self.critical_ky and ctx.depletion_mm >= ctx.raw_mm:
            return ctx.depletion_mm
            
        return 0.0

    def reset(self) -> None:
        pass
