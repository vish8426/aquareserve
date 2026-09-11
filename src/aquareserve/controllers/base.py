"""Controller interface for irrigation strategies.

A controller looks at a zone's state on a given day and returns the *net* irrigation depth (mm) it would like applied to that zone.
The simulation engine then caps that request by the zone's application-rate limit, irrigation efficiency and the shared finite reserve, so a controller never has to know about reserve accounting itself.

All strategies (rainfed, fixed, threshold, smart rule, MPC, RL) implement this one interface, which keeps the metrics harness and comparison study controller-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..config.schema import GrowthStage, ReserveStrategy


@dataclass(frozen=True)
class ZoneControlContext:
    """Everything a controller may use to decide a zone's irrigation for one day."""

    zone_id: str
    day_in_season: int
    stage: GrowthStage

    # root-zone depletion Dr at the start of the day
    depletion_mm: float  

    # readily available water (stress onset threshold)
    raw_mm: float  

    # total available water
    taw_mm: float  

    # reference ET today
    et0_mm: float  

    # potential crop ET today (Kc * ET0)
    crop_et_mm: float  
    days_since_irrigation: int
    max_application_rate_mm_per_day: float
    strategy: ReserveStrategy = ReserveStrategy.RAINFED

    # FAO-33 yield-response factor for the current stage
    stage_ky: float = 0.0  


@runtime_checkable
class Controller(Protocol):
    """An irrigation control strategy."""

    name: str

    def request_mm(self, ctx: ZoneControlContext) -> float:
        """Return the desired net irrigation depth (mm) for this zone today."""
        ...

    def reset(self) -> None:
        """Clear any per-run internal state (called before each simulation run)."""
        ...
