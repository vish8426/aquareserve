"""Crop development: FAO-56 crop coefficient (Kc) curve, growth stage and root depth.

Given a :class:`CropModel` (Kc anchor points + stage lengths + root depth), this produces, for any day since planting:

    * Kc(day)           - the single crop coefficient along the FAO-56 four-stage curve
    * stage(day)        - which growth stage the crop is in (used for yield weighting)
    * root_depth_m(day) - effective rooting depth (grows initial -> max by end of development)

Crop water demand is then ET_c = Kc * ET0 (the caller supplies ET0).
"""

from __future__ import annotations

from ..config.schema import CropModel, GrowthStage


class CropCurve:
    """FAO-56 development curve derived from a crop parameter pack."""

    def __init__(self, crop: CropModel):
        self.crop = crop
        s = crop.stage_days
        self.l_ini = s.initial
        self.l_dev = s.development
        self.l_mid = s.mid
        self.l_late = s.late
        self.total_days = s.total

        # Stage boundaries (day index at which each stage ends)
        self._end_ini = self.l_ini
        self._end_dev = self.l_ini + self.l_dev
        self._end_mid = self.l_ini + self.l_dev + self.l_mid
        self._end_late = self.total_days

    # -- Crop coefficient --------------------------------------------------
    def kc(self, day: int) -> float:
        """Single crop coefficient Kc for a given day since planting (FAO-56)."""
        kc = self.crop.kc
        d = max(0, day)

        if d < self._end_ini:
            return kc.initial

        # linear rise Kc_ini -> Kc_mid
        if d < self._end_dev:  
            frac = (d - self._end_ini) / self.l_dev

            return kc.initial + frac * (kc.mid - kc.initial)

        if d < self._end_mid:
            return kc.mid

        # linear fall Kc_mid -> Kc_end
        if d < self._end_late:  
            frac = (d - self._end_mid) / self.l_late
            
            return kc.mid + frac * (kc.end - kc.mid)

        # post-maturity
        return kc.end  

    # -- Growth stage ------------------------------------------------------
    def stage(self, day: int) -> GrowthStage:
        d = max(0, day)

        if d < self._end_ini:
            return GrowthStage.INITIAL

        if d < self._end_dev:
            return GrowthStage.DEVELOPMENT

        if d < self._end_mid:
            return GrowthStage.MID

        return GrowthStage.LATE

    # -- Root depth --------------------------------------------------------
    def root_depth_m(self, day: int) -> float:
        """Effective rooting depth: grows linearly to max by the end of development."""
        rd = self.crop.root_depth
        d = max(0, day)

        # roots reach max by end of development stage
        grow_period = self._end_dev  

        if d >= grow_period or grow_period <= 0:
            return rd.max_m

        frac = d / grow_period
        
        return rd.initial_m + frac * (rd.max_m - rd.initial_m)

    def crop_demand_mm(self, day: int, et0_mm: float) -> float:
        """Potential crop evapotranspiration ET_c = Kc(day) * ET0 [mm/day]."""
        return self.kc(day) * et0_mm
