"""Root-zone soil water balance (FAO-56 water-accounting method).

Tracks root-zone depletion ``Dr`` [mm] - how much water has been drawn below field capacity.
The balance follows FAO-56 (Chapter 8):

    Dr_i = Dr_{i-1} - (P - RO) - I + ET_a + DP

where P = precipitation, RO = runoff, I = irrigation, ET_a = actual crop ET and DP = deep percolation (water draining below the root zone once the profile is full).

Water stress reduces ET below potential via the FAO-56 stress coefficient Ks:

    Ks = 1                      if Dr <= RAW      (readily available water)
    Ks = (TAW - Dr)/(TAW - RAW) if Dr >  RAW      (linearly down to 0 at wilting)

TAW = total available water in the root zone; RAW = p * TAW.
This module is deliberately state-machine simple and mass-conservative - verified by the property tests in ``tests/test_soil_water.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SoilWaterStep:
    """Outcome of a single daily step."""

    # Dr after the step
    depletion_mm: float  

    # Ks used for this step
    stress_coefficient: float  

    # ET_a = Ks * ET_c
    actual_et_mm: float  

    # deep percolation DP
    drainage_mm: float

    # RO  
    runoff_mm: float  

    # Dr / TAW in [0, 1]
    fraction_depleted: float  


class SoilWaterBalance:
    """Single root-zone bucket following the FAO-56 depletion method.

    Parameters
    ----------
    taw_mm : total available water in the root zone [mm].
    depletion_fraction_p : FAO-56 p - fraction of TAW that can be depleted before the crop experiences water stress.
    initial_depletion_mm : depletion at the start of the run [mm].
    """

    def __init__(self, taw_mm: float, depletion_fraction_p: float, initial_depletion_mm: float = 0.0):
        if taw_mm <= 0:
            raise ValueError("taw_mm must be positive")

        if not 0 < depletion_fraction_p < 1:
            raise ValueError("depletion_fraction_p must be in (0, 1)")

        self.taw = taw_mm
        self.p = depletion_fraction_p
        self.dr = min(max(0.0, initial_depletion_mm), taw_mm)

    @property
    def raw_mm(self) -> float:
        """Readily available water = p * TAW [mm]."""
        return self.p * self.taw

    def stress_coefficient(self, depletion_mm: float | None = None) -> float:
        """FAO-56 water-stress coefficient Ks for the given (or current) depletion."""
        dr = self.dr if depletion_mm is None else depletion_mm

        if dr <= self.raw_mm:
            return 1.0

        ks = (self.taw - dr) / (self.taw - self.raw_mm)
        
        return max(0.0, min(1.0, ks))

    def step(
        self,
        rain_mm: float,
        crop_et_mm: float,
        irrigation_mm: float = 0.0,
        runoff_mm: float = 0.0,
    ) -> SoilWaterStep:
        """Advance the balance by one day and return the outcome.

        ``crop_et_mm`` is the *potential* crop ET (ET_c); it is reduced by Ks when the soil is dry.
        Mass is conserved: any water beyond field capacity leaves as deep percolation (drainage).
        """
        runoff_mm = max(0.0, runoff_mm)
        water_in = max(0.0, rain_mm) - runoff_mm + max(0.0, irrigation_mm)

        # Stress is evaluated on the depletion at the start of the day.
        ks = self.stress_coefficient(self.dr)
        eta = ks * max(0.0, crop_et_mm)

        # Deep percolation: water that would push the profile above field capacity.
        drainage = max(0.0, water_in - eta - self.dr)

        dr_new = self.dr - water_in + eta + drainage
        dr_new = max(0.0, min(self.taw, dr_new))
        self.dr = dr_new

        return SoilWaterStep(
            depletion_mm=dr_new,
            stress_coefficient=ks,
            actual_et_mm=eta,
            drainage_mm=drainage,
            runoff_mm=runoff_mm,
            fraction_depleted=dr_new / self.taw,
        )


def taw_from_soil(total_available_water_mm_per_m: float, root_depth_m: float) -> float:
    """Total available water [mm] for a root zone of the given depth."""
    return total_available_water_mm_per_m * root_depth_m
