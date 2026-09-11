"""Baseline irrigation controllers.

* RainfedController - never irrigates (the do-nothing baseline).
* FixedScheduleController - a set depth every N days regardless of soil state.
* ThresholdController - the classic "irrigate to field capacity when the readily-available water is used up" soil-moisture rule.

These make no use of growth stage, crop value or the reserve level; the smart rule-based, MPC and RL controllers improve on them.
"""

from __future__ import annotations

from .base import ZoneControlContext


class RainfedController:
    """No irrigation at all. Yield is whatever the rain delivers."""

    name = "rainfed"

    def request_mm(self, ctx: ZoneControlContext) -> float:
        return 0.0

    def reset(self) -> None:
        pass


class FixedScheduleController:
    """Apply a fixed net depth every ``interval_days``, ignoring soil state."""

    def __init__(self, depth_mm: float = 20.0, interval_days: int = 10):
        if depth_mm < 0:
            raise ValueError("depth_mm must be non-negative")

        if interval_days < 1:
            raise ValueError("interval_days must be >= 1")

        self.depth_mm = depth_mm
        self.interval_days = interval_days
        self.name = f"fixed_{depth_mm:g}mm_{interval_days}d"

    def request_mm(self, ctx: ZoneControlContext) -> float:

        # Irrigate on the first day and every interval thereafter.
        if ctx.day_in_season % self.interval_days == 0:
            return self.depth_mm

        return 0.0

    def reset(self) -> None:
        pass


class ThresholdController:
    """Soil-moisture threshold: refill to field capacity once depletion reaches a fraction of TAW.

    ``trigger_fraction`` is the depletion (as a fraction of TAW) at which irrigation starts.
    It defaults to the crop's readily-available-water threshold (RAW/TAW), i.e. irrigate exactly when the crop would otherwise begin to experience stress.
    When triggered, it requests enough to bring depletion back to zero (the engine's application-rate cap spreads a large refill over several days).
    """

    def __init__(self, trigger_fraction: float | None = None):
        if trigger_fraction is not None and not 0 < trigger_fraction < 1:
            raise ValueError("trigger_fraction must be in (0, 1)")

        self.trigger_fraction = trigger_fraction
        self.name = "threshold" if trigger_fraction is None else f"threshold_{trigger_fraction:g}"

    def request_mm(self, ctx: ZoneControlContext) -> float:
        threshold_mm = (ctx.raw_mm if self.trigger_fraction is None else self.trigger_fraction * ctx.taw_mm)

        if ctx.depletion_mm >= threshold_mm:

            # refill to field capacity (capped by engine)
            return ctx.depletion_mm  

        return 0.0

    def reset(self) -> None:
        pass
