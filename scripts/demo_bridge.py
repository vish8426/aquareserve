"""AquaReserve tabletop-demo bridge (software-in-the-loop).

A tiny FastAPI companion the ESP32 (or the software emulator) posts its soil-moisture reading to.
It runs the same decision *family* as the aquareserve controllers - a soil-moisture threshold with a critical-stage boost and a finite-reserve guard - and returns how long to run the pump.
The finite reserve is tracked here, in software, so the physical toy is driven by the software, which is the whole point of the demonstration.

It depends only on FastAPI, so it runs on a laptop or a Raspberry Pi without the full modeling stack.
A fuller build can import ``aquareserve.controllers`` directly to drive the toy from the live twin.

Run:
    uvicorn scripts.demo_bridge:app --host 0.0.0.0 --port 8500
    # or simply:  python scripts/demo_bridge.py
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from fastapi import FastAPI
from pydantic import BaseModel, Field

# Tuning (override with environment variables).
# These mirror the ThresholdController and SmartCriticalStageController: irrigate when the soil dries past a trigger and protect harder during a critical growth stage.
TRIGGER_PCT = float(os.environ.get("DEMO_TRIGGER_PCT", 35))
CRITICAL_TRIGGER_PCT = float(os.environ.get("DEMO_CRITICAL_TRIGGER_PCT", 45))
PUMP_ML_PER_S = float(os.environ.get("DEMO_PUMP_ML_PER_S", 8))
PULSE_S = float(os.environ.get("DEMO_PULSE_S", 2))
INITIAL_RESERVE_ML = float(os.environ.get("DEMO_INITIAL_RESERVE_ML", 500))

app = FastAPI(title="AquaReserve demo bridge", version="0.1.0")


@dataclass
class ZoneState:
    reserve_ml: float
    initial_ml: float
    waterings: int = 0
    drawn_ml: float = 0.0
    last_moisture_pct: float | None = None


_zones: dict[str, ZoneState] = {}


def _zone(name: str) -> ZoneState:
    if name not in _zones:
        _zones[name] = ZoneState(INITIAL_RESERVE_ML, INITIAL_RESERVE_ML)
    return _zones[name]


class Reading(BaseModel):
    zone: str = "tray-1"
    moisture_pct: float = Field(ge=0, le=100)
    critical_stage: bool = False

    # optional client-authoritative override
    reserve_ml: float | None = None  


class Decision(BaseModel):
    zone: str
    pump_ms: int
    reason: str
    reserve_ml_after: float
    reserve_pct: float
    moisture_pct: float


@app.post("/demo/decide", response_model=Decision)
def decide(r: Reading) -> Decision:
    """Decide whether (and how long) to run the pump for one zone, spending the finite reserve."""
    z = _zone(r.zone)

    if r.reserve_ml is not None:
        z.reserve_ml = max(0.0, r.reserve_ml)
    z.last_moisture_pct = r.moisture_pct

    trigger = CRITICAL_TRIGGER_PCT if r.critical_stage else TRIGGER_PCT

    if r.moisture_pct >= trigger:
        pump_ms, reason = 0, "moist enough (at or above the trigger)"
    elif z.reserve_ml <= 0:
        pump_ms, reason = 0, "reserve exhausted - crop now unprotected"
    else:
        want_ml = PUMP_ML_PER_S * PULSE_S
        give_ml = min(want_ml, z.reserve_ml)
        pump_ms = int(round((give_ml / PUMP_ML_PER_S) * 1000))
        z.reserve_ml -= give_ml
        z.drawn_ml += give_ml
        z.waterings += 1
        reason = "watering (critical stage)" if r.critical_stage else "watering (below trigger)"

        if give_ml < want_ml:
            reason += " - last of the reserve"

    return Decision(
        zone=r.zone,
        pump_ms=pump_ms,
        reason=reason,
        reserve_ml_after=round(z.reserve_ml, 1),
        reserve_pct=round(100 * z.reserve_ml / z.initial_ml, 1) if z.initial_ml > 0 else 0.0,
        moisture_pct=r.moisture_pct,
    )


class ResetRequest(BaseModel):
    zone: str | None = None
    initial_ml: float | None = None


@app.post("/demo/reset")

def reset(req: ResetRequest) -> dict:
    """Refill the reserve for one zone (or all zones) so the demo can be re-run."""
    init = req.initial_ml if req.initial_ml is not None else INITIAL_RESERVE_ML

    if req.zone:
        _zones[req.zone] = ZoneState(init, init)
    else:
        for k in list(_zones):
            _zones[k] = ZoneState(init, init)
        if not _zones:
            _zones["tray-1"] = ZoneState(init, init)
            
    return {"status": "reset", "initial_ml": init}


@app.get("/demo/state")
def state() -> dict:
    return {z: asdict(s) for z, s in _zones.items()}


@app.get("/")
def root() -> dict:
    return {
        "service": "aquareserve-demo-bridge",
        "zones": len(_zones),
        "trigger_pct": TRIGGER_PCT,
        "critical_trigger_pct": CRITICAL_TRIGGER_PCT,
        "pump_ml_per_s": PUMP_ML_PER_S,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8500")))
