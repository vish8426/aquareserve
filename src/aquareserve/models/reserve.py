"""Finite backup water reserve dynamics.

The reserve is a single aggregate store (farm dam + harvested rainwater + bore allocation) measured in cubic metres.
Each day it:

  * gains water from rainwater capture (rain depth over a catchment area, scaled by a runoff coefficient) and any steady baseflow (e.g. a licensed bore allocation);
  * spills any excess above capacity;
  * loses water to open water evaporation from the dam surface;
  * supplies irrigation withdrawals, capped so the volume never goes negative.

Open water evaporation is estimated from reference ET0.
FAO-56 relates ET0 to Class-A pan evaporation by ET0 ~= 0.7 * E_pan, and open-water evaporation is Kp * E_pan, so

    E_open_mm = pan_coefficient * (ET0 / 0.7)

With the default pan_coefficient of 0.7 this gives E_open ~= ET0, a reasonable first estimate for a large water body - raising pan_coefficient increases loss.

Units: volumes in m3, depths in mm, areas in m2. 1 mm over 1 m2 = 0.001 m3.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config.schema import Reserve

# FAO-56 approximate ratio ET0 = 0.7 * pan evaporation.
_ET0_TO_PAN = 0.7

# 1 mm depth over 1 m2 = 0.001 m3
_MM_M2_TO_M3 = 0.001  


@dataclass(frozen=True)
class ReserveStep:
    """Outcome of a single days reserve balance."""

    # end-of-day stored volume
    volume_m3: float  

    # rainwater harvested this day
    capture_m3: float  

    # steady inflow (e.g. bore) this day
    baseflow_m3: float  

    # open-water evaporation loss
    evaporation_m3: float 

    # water actually supplied for irrigation 
    withdrawal_m3: float  

    # overflow lost above capacity
    spill_m3: float  

    # volume / capacity in [0, 1]
    fraction_full: float  


class ReserveModel:
    """Daily finite-reserve balance driven by an AquaReserve :class:`Reserve` config."""

    def __init__(self, reserve: Reserve):
        self.capacity = reserve.capacity_m3
        self.volume = min(reserve.initial_volume_m3, reserve.capacity_m3)
        self.surface_area_m2 = reserve.surface_area_m2
        self.pan_coefficient = reserve.pan_coefficient
        self._sources = reserve.sources

    @property
    def fraction_full(self) -> float:
        return self.volume / self.capacity if self.capacity > 0 else 0.0

    def capture_from_rain(self, rain_mm: float) -> float:
        """Rainwater harvested [m3] from all catchment sources for a rain depth."""
        rain_mm = max(0.0, rain_mm)
        total = 0.0

        for s in self._sources:
            if s.catchment_area_m2 and s.runoff_coefficient:
                total += rain_mm * s.catchment_area_m2 * s.runoff_coefficient * _MM_M2_TO_M3

        return total

    def baseflow(self) -> float:
        """Steady daily inflow [m3] from sources such as a bore allocation."""
        return sum(s.daily_inflow_m3 for s in self._sources if s.daily_inflow_m3)

    def open_water_evaporation(self, et0_mm: float) -> float:
        """Open-water evaporation loss [m3] for the day from reference ET0."""
        evap_mm = self.pan_coefficient * (max(0.0, et0_mm) / _ET0_TO_PAN)

        return evap_mm * self.surface_area_m2 * _MM_M2_TO_M3

    def available_for_withdrawal(self, rain_mm: float, et0_mm: float) -> float:
        """Volume [m3] available for irrigation today, after capture, spill and evaporation but before any withdrawal.
        Does not mutate the reserve; used by the engine to allocate a shared reserve across zones.
        """
        v = min(self.volume + self.capture_from_rain(rain_mm) + self.baseflow(), self.capacity)
        v -= min(self.open_water_evaporation(et0_mm), v)

        return v

    def step(self, rain_mm: float, et0_mm: float, withdrawal_request_m3: float = 0.0) -> ReserveStep:
        """Advance the reserve one day.

        Order: add inflow, spill above capacity, evaporate (bounded by stored water), then supply the withdrawal request (bounded by remaining water).
        Returns the day's flows and the end volume.
        """
        capture = self.capture_from_rain(rain_mm)
        base = self.baseflow()

        # Inflow, capped at capacity (excess spills).
        v = self.volume + capture + base
        spill = max(0.0, v - self.capacity)
        v = min(v, self.capacity)

        # Evaporation cannot remove more than is present.
        evap = min(self.open_water_evaporation(et0_mm), v)
        v -= evap

        # Withdrawal cannot exceed remaining water.
        withdrawal = min(max(0.0, withdrawal_request_m3), v)
        v -= withdrawal

        self.volume = v
        
        return ReserveStep(
            volume_m3=v,
            capture_m3=capture,
            baseflow_m3=base,
            evaporation_m3=evap,
            withdrawal_m3=withdrawal,
            spill_m3=spill,
            fraction_full=self.fraction_full,
        )
