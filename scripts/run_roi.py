"""Cost / ROI analysis: payback, NPV, and the software vs bigger dam trade.

Runs every controller across a normal and a severe drought year, values the production uplift at farmgate prices, and reports capex, expected annual benefit, payback and NPV.
It then quantifies how much extra dam the naive rule would need to match the MPC, valuing the storage the smart software displaces.
Saves a figure.

Usage:
    python scripts/run_roi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.config.loader import load_economics  

from aquareserve.controllers import (  
    MPCController,
    OracleController,
    RainfedController,
    SmartCriticalStageController,
    ThresholdController,
)

from aquareserve.metrics import (  
    compute_metrics,
    dam_capacity_to_match,
    evaluate,
    system_capex,
)

from aquareserve.simulation import SimulationEngine  
from aquareserve.weather import load_weather  

PLANTING = "2000-05-01"


def _controllers(sc, wx):
    return [
        ("threshold", ThresholdController()),
        ("smart_rule", SmartCriticalStageController()),
        ("mpc", MPCController(sc)),
        ("oracle", OracleController(sc, wx, PLANTING)),
    ]


def main() -> int:
    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    econ = load_economics(REPO_ROOT / "config" / "economics.example.yaml")
    wn = load_weather(sc.climate, scenario_name="normal", base_dir=str(REPO_ROOT))
    ws = load_weather(sc.climate, scenario_name="severe", base_dir=str(REPO_ROOT))
    en = SimulationEngine(sc, wn, planting_date=PLANTING)
    es = SimulationEngine(sc, ws, planting_date=PLANTING)
    rf_n = compute_metrics(en.run(RainfedController()), sc)
    rf_s = compute_metrics(es.run(RainfedController()), sc)

    cur = econ.currency

    print(f"AquaReserve cost/ROI - {cur}, {econ.horizon_years}-yr horizon, "
          f"{econ.discount_rate:.0%} discount, {econ.severe_year_probability:.0%} severe-year prob")
    print(f"System capex: {cur} {system_capex(sc, econ):,.0f} "
          f"({sc.farm.reserve.capacity_m3/1000:.0f} ML storage + hardware)\n")
    print(f"{'controller':11s} {'benefit/yr':>12s} {'payback':>9s} {'NPV (10yr)':>13s}")

    econ_by_ctrl = {}

    for name, ctrl in _controllers(sc, wn):
        cn = compute_metrics(en.run(ctrl), sc)
        ctrl2 = dict(_controllers(sc, ws))[name]
        cs = compute_metrics(es.run(ctrl2), sc)
        r = evaluate(cn, rf_n, cs, rf_s, sc, econ)
        econ_by_ctrl[name] = (r, cn, cs)
        pb = f"{r.payback_years:.1f} yr" if r.payback_years else "never"

        print(f"{name:11s} {cur} {r.expected_annual_benefit:>8,.0f} {pb:>9s} {cur} {r.npv:>9,.0f}")

    # Software vs bigger dam: how much dam would 'threshold' need to match MPC (severe)?
    mpc_sev_prod = econ_by_ctrl["mpc"][2].total_production_t
    prod_by_cap = {}

    for cap_ml in [20, 25, 30, 35, 40, 50, 60]:
        sc2 = sc.model_copy(deep=True)
        sc2.farm.reserve.capacity_m3 = cap_ml * 1000.0
        sc2.farm.reserve.initial_volume_m3 = 0.6 * cap_ml * 1000.0
        eng = SimulationEngine(sc2, ws, planting_date=PLANTING)
        prod_by_cap[float(cap_ml)] = compute_metrics(eng.run(ThresholdController()), sc2).total_production_t

    needed_ml = dam_capacity_to_match(mpc_sev_prod, prod_by_cap)
    
    if needed_ml:
        extra_ml = needed_ml - sc.farm.reserve.capacity_m3 / 1000.0
        saved = extra_ml * 1000.0 * econ.costs.storage_capex_per_m3

        print(f"\nSoftware vs bigger dam (severe year): the naive rule needs a "
              f"{needed_ml:.0f} ML dam to match the MPC's {mpc_sev_prod:.0f} t at 20 ML.")

        print(f"  => the MPC software displaces ~{extra_ml:.0f} ML of storage, "
              f"worth {cur} {saved:,.0f} in avoided dam capex.")

    _plot(econ_by_ctrl, cur, REPO_ROOT / "outputs" / "roi_comparison.png")

    return 0


def _plot(econ_by_ctrl, cur, out: Path) -> None:

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

    except ImportError:
        return

    names = list(econ_by_ctrl)
    npvs = [econ_by_ctrl[n][0].npv for n in names]
    paybacks = [econ_by_ctrl[n][0].payback_years or 0 for n in names]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.5))

    a1.bar(names, npvs, color="#27ae60")
    a1.set_ylabel(f"NPV ({cur})")
    a1.set_title("Net present value by controller", loc="left", fontsize=10)
    a1.tick_params(axis="x", labelrotation=15)
    a2.bar(names, paybacks, color="#2980b9")
    a2.set_ylabel("payback (years)")
    a2.set_title("Payback period by controller", loc="left", fontsize=10)
    a2.tick_params(axis="x", labelrotation=15)

    fig.suptitle("AquaReserve - cost/ROI by controller (real 2000 season)", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    
    print(f"figure saved -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
