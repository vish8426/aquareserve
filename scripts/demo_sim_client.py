"""Software-only ESP32 emulator for the AquaReserve demo bridge.

Pretends to be the tabletop rig: a patch of soil that dries over time, posting its moisture to the bridge each step and applying whatever pump command comes back.
This lets you run and test the whole software-in-the-loop demo with no hardware at all - handy for a laptop-only demo or a CI check.
Uses only the standard library.

Run the bridge first (``python scripts/demo_bridge.py``), then:
    python scripts/demo_sim_client.py --url http://localhost:8500 --steps 40
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


def post(url: str, path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url + path, data=data, headers={"Content-Type": "application/json"}
    )
    # noqa: S310 - local demo endpoint
    with urllib.request.urlopen(req, timeout=5) as resp:  
        return json.loads(resp.read())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://localhost:8500")
    ap.add_argument("--zone", default="tray-1")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--initial-ml", type=float, default=500.0)
    ap.add_argument("--dry-per-step", type=float, default=4.0, help="%% soil drying per step")
    ap.add_argument("--absorb-per-ml", type=float, default=1.2, help="%% moisture gained per ml")
    ap.add_argument("--pump-ml-per-s", type=float, default=8.0)
    ap.add_argument("--sleep", type=float, default=0.2)

    a = ap.parse_args()

    post(a.url, "/demo/reset", {"zone": a.zone, "initial_ml": a.initial_ml})

    moisture = 60.0

    print(f"{'step':>4} {'moist%':>7} {'pump_ms':>8} {'reserve%':>9}  reason")

    for i in range(1, a.steps + 1):

        # a sensitive growth window mid-run
        critical = a.steps // 3 <= i < 2 * a.steps // 3  
        d = post(a.url, "/demo/decide", {
            "zone": a.zone, "moisture_pct": round(moisture, 1), "critical_stage": critical,
        })

        delivered_ml = d["pump_ms"] / 1000.0 * a.pump_ml_per_s
        moisture = min(100.0, moisture + delivered_ml * a.absorb_per_ml)
        tag = " [critical]" if critical else ""
        print(f"{i:>4} {moisture:>7.1f} {d['pump_ms']:>8} {d['reserve_pct']:>8.1f}%  {d['reason']}{tag}")

        # dry out before the next reading
        moisture = max(0.0, moisture - a.dry_per_step)  
        time.sleep(a.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
