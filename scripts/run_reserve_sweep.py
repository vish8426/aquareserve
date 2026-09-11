"""Reserve-size sweep: how days-of-support and production scale with dam size.

Sweeps the reserve capacity (initial fill held at 60%) under a severe drought year and records, for the naive threshold and the smart controller, how many days the reserve keeps usable water and the resulting farm production.
Saves a figure.

Usage:
    python scripts/run_reserve_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.controllers import SmartCriticalStageController, ThresholdController  
from aquareserve.metrics import compute_metrics  
from aquareserve.simulation import SimulationEngine  
from aquareserve.weather import load_weather  

SIZES_ML = [5, 10, 15, 20, 30, 40, 60]
PLANTING = "2000-05-01"


def main() -> int:
    base = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    wx = load_weather(base.climate, scenario_name="severe", base_dir=str(REPO_ROOT))
    controllers = {"threshold": ThresholdController, "smart_rule": SmartCriticalStageController}
    season_days = max(base.crops[z.crop].stage_days.total for z in base.farm.zones)

    print(f"Reserve-size sweep - severe drought, {season_days}-day season, 24 ha mixed farm")
    print(f"{'reserve(ML)':>11s}  {'threshold: support(d) / prod(t)':>32s}  {'smart: support(d) / prod(t)':>28s}")

    data = {name: {"support": [], "prod": []} for name in controllers}

    for cap_ml in SIZES_ML:
        sc = base.model_copy(deep=True)
        sc.farm.reserve.capacity_m3 = cap_ml * 1000.0
        sc.farm.reserve.initial_volume_m3 = 0.6 * cap_ml * 1000.0
        engine = SimulationEngine(sc, wx, planting_date=PLANTING)
        row = {}

        for name, cls in controllers.items():
            r = engine.run(cls())
            m = compute_metrics(r, sc)
            support = r.reserve_survival_days()
            data[name]["support"].append(support)
            data[name]["prod"].append(m.total_production_t)
            row[name] = (support, m.total_production_t)

        print(f"{cap_ml:11d}  {row['threshold'][0]:12d}d /{row['threshold'][1]:8.0f}t  "
              f"{row['smart_rule'][0]:12d}d /{row['smart_rule'][1]:8.0f}t")

    _plot(SIZES_ML, data, season_days, REPO_ROOT / "outputs" / "reserve_size_sweep.png")

    return 0


def _plot(sizes, data, season_days, out: Path) -> None:

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

    except ImportError:
        return

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6))

    for name, color in [("threshold", "#c0392b"), ("smart_rule", "#27ae60")]:
        a1.plot(sizes, data[name]["support"], "o-", color=color, label=name)
        a2.plot(sizes, data[name]["prod"], "o-", color=color, label=name)

    a1.axhline(season_days, color="#7f8c8d", ls=":", lw=1, label=f"full season ({season_days} d)")
    a1.axvline(20, color="#2980b9", ls="--", lw=1, label="current 20 ML")
    a1.set_xlabel("reserve capacity (ML)")
    a1.set_ylabel("days reserve holds usable water")
    a1.set_title("Days of support vs reserve size (severe drought)", fontsize=10, loc="left")
    a1.legend(fontsize=8)
    a2.axvline(20, color="#2980b9", ls="--", lw=1)
    a2.set_xlabel("reserve capacity (ML)")
    a2.set_ylabel("total farm production (t)")
    a2.set_title("Production vs reserve size (severe drought)", fontsize=10, loc="left")
    a2.legend(fontsize=8)

    fig.suptitle("AquaReserve - reserve-size sweep on the real 2000 severe-drought season", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)

    print(f"\nfigure saved -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
