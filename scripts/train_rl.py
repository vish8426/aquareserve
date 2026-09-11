"""Train the RL comparison policy (CEM) and benchmark it against the controller ladder.

Trains a linear policy by the Cross-Entropy Method directly on the simulation engine (normal + severe 2000 season), then evaluates every controller on the same engine and saves a comparison figure.
Use committed weights by default; pass --retrain to search afresh.

Usage:
    python scripts/train_rl.py [--retrain] [--save]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  

from aquareserve.controllers import (  
    MPCController,
    OracleController,
    RainfedController,
    SmartCriticalStageController,
    StochasticMPCController,
    ThresholdController,
)

from aquareserve.metrics import compute_metrics  
from aquareserve.rl import LinearPolicyController, cem_train  
from aquareserve.simulation import SimulationEngine  
from aquareserve.weather import load_weather  

PLANTING = "2000-05-01"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrain", action="store_true", help="search weights instead of using committed ones")
    ap.add_argument("--save", action="store_true", help="save searched weights to outputs/rl_weights.npy")

    args = ap.parse_args()

    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    wx = {s: load_weather(sc.climate, scenario_name=s, base_dir=str(REPO_ROOT)) for s in ("normal", "severe")}

    if args.retrain:

        print("Training RL policy by Cross-Entropy Method (normal + severe)...")

        res = cem_train(sc, [wx["normal"], wx["severe"]], planting=PLANTING, iterations=22, population=22, seed=5)
        rl = LinearPolicyController(sc, res.weights)

        print(f"  normalised return {res.best_return:.3f}; weights = {np.round(res.weights, 3).tolist()}")

        if args.save:
            (REPO_ROOT / "outputs").mkdir(exist_ok=True)
            np.save(REPO_ROOT / "outputs" / "rl_weights.npy", res.weights)

            print("  saved -> outputs/rl_weights.npy (paste into rl/_pretrained.py to commit)")

    else:
        rl = LinearPolicyController.pretrained(sc)

        print("Using committed CEM-trained weights (rl/_pretrained.py).")

    results: dict[str, dict[str, float]] = {}

    for scen in ("normal", "severe"):

        eng = SimulationEngine(sc, wx[scen], planting_date=PLANTING)

        ctrls = [
            ("rainfed", RainfedController()),
            ("threshold", ThresholdController()),
            ("smart_rule", SmartCriticalStageController()),
            ("mpc", MPCController(sc)),
            ("stochastic_mpc", StochasticMPCController(sc)),
            ("rl_cem", rl),
            ("oracle", OracleController(sc, wx[scen], PLANTING)),
        ]

        results[scen] = {}

        print(f"\n=== {scen.upper()} (production t) ===")

        for name, c in ctrls:
            p = compute_metrics(eng.run(c), sc).total_production_t
            results[scen][name] = p

            print(f"  {name:15s} {p:6.1f}")

    _plot(results, REPO_ROOT / "outputs" / "rl_comparison.png")

    return 0


def _plot(results, out: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

    except ImportError:
        return

    ctrls = ["rainfed", "threshold", "smart_rule", "mpc", "stochastic_mpc", "rl_cem", "oracle"]

    x = np.arange(len(ctrls))
    w = 0.38
    
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.bar(x - w / 2, [results["normal"][c] for c in ctrls], w, label="normal year", color="#4a90d9")
    ax.bar(x + w / 2, [results["severe"][c] for c in ctrls], w, label="severe drought", color="#c0392b")
    ax.set_xticks(x)
    ax.set_xticklabels(ctrls, rotation=15)
    ax.set_ylabel("total farm production (t)")
    ax.set_title("AquaReserve - RL policy vs the controller ladder (real 2000 season)", fontweight="bold")
    ax.legend()

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    
    print(f"\nfigure saved -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
