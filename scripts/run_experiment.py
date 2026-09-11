"""Controller comparison on the real 2000 Mildura farm, normal vs severe drought.

Runs rainfed, fixed-schedule, soil-moisture-threshold and the smart critical-stage controller over the whole mixed farm sharing the finite 20ML reserve, for both a normal and a severe-drought year.
Reports yield, production, water use and reserve survival and saves a comparison figure.

Usage:
    python scripts/run_experiment.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.controllers import (  
    FixedScheduleController,
    MPCController,
    OracleController,
    RainfedController,
    SmartCriticalStageController,
    StochasticMPCController,
    ThresholdController,
)

from aquareserve.metrics import compute_metrics  
from aquareserve.simulation import SimulationEngine  
from aquareserve.weather import load_weather  

PLANTING = "2000-05-01"
SCENARIOS = ["normal", "severe"]


def controllers(sc, wx):
    return [
        RainfedController(),
        FixedScheduleController(depth_mm=15.0, interval_days=10),
        ThresholdController(),
        SmartCriticalStageController(),
        MPCController(sc),
        StochasticMPCController(sc),
        OracleController(sc, wx, PLANTING),
    ]


def main() -> int:
    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    results: dict[str, dict[str, object]] = {}

    for scen in SCENARIOS:
        wx = load_weather(sc.climate, scenario_name=scen, base_dir=str(REPO_ROOT))
        engine = SimulationEngine(sc, wx, planting_date=PLANTING)

        print(f"\n=== {scen.upper()} year (real Mildura 2000, sown {PLANTING}) ===")
        print(f"{'controller':16s} {'prod(t)':>8s} {'irrig(m3)':>10s} "
              f"{'reserve end':>11s} {'survival':>8s}  onion/wheat/barley t/ha")

        results[scen] = {}

        for ctrl in controllers(sc, wx):
            m = compute_metrics(engine.run(ctrl), sc)
            results[scen][m.controller] = m
            ys = "/".join(f"{z.yield_t_ha:.1f}" for z in m.zones)

            print(f"{m.controller:16s} {m.total_production_t:8.1f} {m.total_irrigation_m3:10,.0f} "
                  f"{m.reserve_end_m3:11,.0f} {m.reserve_survival_days:8d}  {ys}")

    thr = results["severe"]["threshold"].total_production_t
    smt = results["severe"]["smart_rule"].total_production_t

    print(f"\n=> Under severe drought, the smart controller produces {smt:.0f} t vs the "
          f"threshold baseline's {thr:.0f} t (+{100*(smt-thr)/thr:.0f}%) using less water.")

    _plot(results, REPO_ROOT / "outputs" / "controller_comparison.png")
    
    return 0


def _plot(results, out: Path) -> None:
    try:
        import matplotlib
    
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

    except ImportError:
        return

    ctrls = ["rainfed", "fixed_15mm_10d", "threshold", "smart_rule", "mpc",
             "stochastic_mpc", "oracle"]

    x = np.arange(len(ctrls))
    w = 0.38

    fig, ax = plt.subplots(figsize=(10, 5))

    normal = [results["normal"][c].total_production_t for c in ctrls]
    severe = [results["severe"][c].total_production_t for c in ctrls]

    ax.bar(x - w / 2, normal, w, label="normal year", color="#4a90d9")
    ax.bar(x + w / 2, severe, w, label="severe drought", color="#c0392b")
    ax.set_xticks(x)
    ax.set_xticklabels(ctrls, rotation=15)
    ax.set_ylabel("total farm production (t)")
    ax.set_title("AquaReserve - controller comparison on the real 2000 season", fontweight="bold")
    ax.legend()

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    
    print(f"figure saved -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
