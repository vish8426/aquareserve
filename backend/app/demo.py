"""Stateless decision logic for the live Monitor demo

The product app's Monitor page runs a small in-browser soil emulator and posts each reading here; this returns whether to run the pump and for how long, spending a finite reserve.
It runs the same decision *family* as the aquareserve controllers - a soil-moisture threshold with a critical-stage boost and a finite-reserve guard - so the live demo tells the same story as the study.

It is deliberately stateless: the caller owns the reserve level and passes it in, exactly as the ESP32 firmware does when it sends a client-authoritative ``reserve_ml``.
That keeps the endpoint safe to serve to many users at once with no server-side session. ``scripts/demo_bridge.py`` keeps its own copy of this logic so it can run standalone on a Raspberry Pi with only FastAPI installed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tuning mirrors the ThresholdController and SmartCriticalStageController: irrigate when the soil dries past a trigger and protect harder during a sensitive growth stage.
TRIGGER_PCT = 35.0
CRITICAL_TRIGGER_PCT = 45.0
PUMP_ML_PER_S = 8.0
PULSE_S = 2.0


@dataclass
class Decision:
    pump_ms: int
    watered: bool
    reason: str
    delivered_ml: float
    reserve_ml_after: float
    reserve_pct: float
    moisture_pct: float


def decide(
    moisture_pct: float,
    reserve_ml: float,
    critical_stage: bool = False,
    initial_reserve_ml: float = 500.0,
    pump_ml_per_s: float = PUMP_ML_PER_S,
    pulse_s: float = PULSE_S,
    trigger_pct: float = TRIGGER_PCT,
    critical_trigger_pct: float = CRITICAL_TRIGGER_PCT,
) -> Decision:
    """Decide whether (and how long) to run the pump for one zone, spending the finite reserve."""
    reserve_ml = max(0.0, reserve_ml)
    trigger = critical_trigger_pct if critical_stage else trigger_pct

    if moisture_pct >= trigger:
        pump_ms, give_ml, reason = 0, 0.0, "moist enough (at or above the trigger)"
    elif reserve_ml <= 0:
        pump_ms, give_ml, reason = 0, 0.0, "reserve exhausted - crop now unprotected"
    else:
        want_ml = pump_ml_per_s * pulse_s
        give_ml = min(want_ml, reserve_ml)
        pump_ms = int(round((give_ml / pump_ml_per_s) * 1000))
        reason = "watering (critical stage)" if critical_stage else "watering (below trigger)"
        if give_ml < want_ml:
            reason += " - last of the reserve"

    reserve_after = max(0.0, reserve_ml - give_ml)
    reserve_pct = round(100 * reserve_after / initial_reserve_ml, 1) if initial_reserve_ml > 0 else 0.0
    return Decision(
        pump_ms=pump_ms,
        watered=pump_ms > 0,
        reason=reason,
        delivered_ml=round(give_ml, 1),
        reserve_ml_after=round(reserve_after, 1),
        reserve_pct=reserve_pct,
        moisture_pct=round(moisture_pct, 1),
    )
