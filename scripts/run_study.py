"""Comparison and sensitivity study.

Reads the precomputed results matrix (``data/results/matrix.csv``) plus the scenario and economics config, then produces the study figures and summary tables for three sensitivity dimensions:

  1. Reserve size - production and reserve-survival vs reserve capacity (5-40ML).
  2. Drought severity - production and yield saved by controller across normal / moderate / severe seasons, at the 20ML design reserve.
  3. Economics - payback and NPV sensitivity to crop prices, discount rate and the severe-year probability.

Nothing here runs the engine: it is pure post-processing of the precomputed store, so the whole study is fast and reproducible.
Figures are written to ``docs/diagrams/study/`` and a machine-readable ``study_summary.json`` captures the headline numbers used in the report.

Usage: python scripts/run_study.py (after scripts/run_matrix.py has built the store)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

# noqa: E402
import matplotlib.pyplot as plt  
import pandas as pd  

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.config.loader import load_economics  

DESIGN_ML = 20.0
DEPLOYABLE = ["threshold", "smart_rule", "mpc", "stochastic_mpc", "rl_cem"]
LABELS = {
    "rainfed": "Rainfed", "threshold": "Threshold", "smart_rule": "Smart-stage",
    "mpc": "MPC", "stochastic_mpc": "Robust MPC", "rl_cem": "RL (CEM)", "oracle": "Oracle",
}
COLORS = {
    "rainfed": "#9e9e9e", "threshold": "#42a5f5", "smart_rule": "#26a69a", "mpc": "#1565c0",
    "stochastic_mpc": "#5e35b1", "rl_cem": "#ef6c00", "oracle": "#78909c",
}
SEVERITY_ORDER = ["normal", "moderate", "severe"]
SEVERITY_LABEL = {"normal": "Normal (2000)", "moderate": "Moderate", "severe": "Severe (2019)"}


def load() -> tuple[pd.DataFrame, dict, dict, object]:
    df = pd.read_csv(REPO_ROOT / "data" / "results" / "matrix.csv")
    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    econ = load_economics(REPO_ROOT / "config" / "economics.example.yaml")
    areas = {z.crop: z.area_ha for z in sc.farm.zones}
    prices = {z.crop: sc.crops[z.crop].price_per_t for z in sc.farm.zones}

    return df, areas, prices, econ


def cell(df, year, controller, reserve_ml=DESIGN_ML):
    r = df[(df.year == year) & (df.controller == controller) & (df.reserve_ml == reserve_ml)]

    return r.iloc[0] if len(r) else None


def value(df, controller, year, areas, prices, price_scale=1.0, reserve_ml=DESIGN_ML) -> float:
    """Farmgate value [AUD] of a controller's production, allowing crop prices to be scaled."""
    row = cell(df, year, controller, reserve_ml)

    if row is None:
        return 0.0

    return sum(row[f"{c}_t_ha"] * areas[c] * prices[c] * price_scale for c in areas)


def capex(econ, n_zones, reserve_ml=DESIGN_ML) -> float:
    storage = reserve_ml * 1000.0 * econ.costs.storage_capex_per_m3

    return storage + n_zones * econ.costs.per_zone_hardware + econ.costs.gateway + econ.costs.install


def economics(df, controller, areas, prices, econ, *, price_scale=1.0, discount=None, p_sev=None, reserve_ml=DESIGN_ML):

    """Return (payback_years|None, npv) blending a normal and a severe season."""
    r = econ.discount_rate if discount is None else discount
    p = econ.severe_year_probability if p_sev is None else p_sev

    fixed = econ.costs.annual_opex + econ.costs.subscription_per_year

    b_norm = value(df, controller, "normal", areas, prices, price_scale, reserve_ml) \
        - value(df, "rainfed", "normal", areas, prices, price_scale, reserve_ml) - fixed

    b_sev = value(df, controller, "severe", areas, prices, price_scale, reserve_ml) \
        - value(df, "rainfed", "severe", areas, prices, price_scale, reserve_ml) - fixed

    expected = (1 - p) * b_norm + p * b_sev

    cap = capex(econ, len(areas), reserve_ml)
    npv = -cap + sum(expected / (1 + r) ** y for y in range(1, econ.horizon_years + 1))
    payback = cap / expected if expected > 0 else None

    return payback, npv


# ---------------------------------------------------------------------------
def fig_reserve_production(df, outdir):
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    sizes = sorted(df.reserve_ml.unique())

    for c in [*DEPLOYABLE, "oracle"]:
        sub = df[(df.year == "severe") & (df.controller == c)].sort_values("reserve_ml")
        ax.plot(sub.reserve_ml, sub.production_t, marker="o", label=LABELS[c], color=COLORS[c], linewidth=2.4 if c == "mpc" else 1.5)

    ax.axvline(DESIGN_ML, color="#b30000", ls="--", lw=1)
    ax.text(DESIGN_ML + 0.4, ax.get_ylim()[0] + 6, "design 20 ML", color="#b30000", fontsize=9)
    ax.set_xlabel("Reserve capacity (ML)")
    ax.set_ylabel("Season production (t)")
    ax.set_title("Reserve-size sensitivity - severe drought (real 2019)")
    ax.set_xticks(sizes)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, ncol=2)

    fig.tight_layout()
    fig.savefig(outdir / "fig_reserve_production.png", dpi=140)

    plt.close(fig)


def fig_reserve_survival(df, outdir):
    fig, ax = plt.subplots(figsize=(7.2, 4.2))

    for c in ["threshold", "smart_rule", "mpc", "stochastic_mpc"]:
        sub = df[(df.year == "severe") & (df.controller == c)].sort_values("reserve_ml")
        ax.plot(sub.reserve_ml, sub.survival_days, marker="s", label=LABELS[c], color=COLORS[c])

    ax.set_xlabel("Reserve capacity (ML)")
    ax.set_ylabel("Reserve survival (days)")
    ax.set_title("Reserve longevity vs capacity - severe drought")
    ax.set_xticks(sorted(df.reserve_ml.unique()))
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(outdir / "fig_reserve_survival.png", dpi=140)

    plt.close(fig)


def fig_severity_production(df, outdir):
    years = [y for y in SEVERITY_ORDER if y in df.year.unique()]
    ctrls = [*DEPLOYABLE, "oracle"]

    import numpy as np

    x = np.arange(len(ctrls))
    w = 0.8 / len(years)
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    shades = {"normal": "#8bc34a", "moderate": "#ffa726", "severe": "#ef5350"}

    for i, y in enumerate(years):
        vals = [cell(df, y, c).production_t for c in ctrls]
        ax.bar(x + i * w, vals, w, label=SEVERITY_LABEL[y], color=shades.get(y, "#90a4ae"))

    ax.set_xticks(x + w * (len(years) - 1) / 2)
    ax.set_xticklabels([LABELS[c] for c in ctrls], rotation=15, fontsize=9)
    ax.set_ylabel("Season production (t) at 20 ML")
    ax.set_title("Production by controller across drought severity", pad=30)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_axisbelow(True)

    ymax = max(cell(df, y, c).production_t for y in years for c in ctrls)

    ax.set_ylim(0, ymax * 1.08)
    ax.legend(fontsize=8, ncol=len(years), loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False, borderaxespad=0.0)

    fig.tight_layout()
    fig.savefig(outdir / "fig_severity_production.png", dpi=140)

    plt.close(fig)


def fig_econ_price(df, areas, prices, econ, outdir):
    scales = [0.6, 0.8, 1.0, 1.2, 1.4]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))

    for c in DEPLOYABLE:
        ys = []

        for s in scales:
            pb, _ = economics(df, c, areas, prices, econ, price_scale=s)
            ys.append(pb if pb is not None else float("nan"))

        ax.plot([int(s * 100) for s in scales], ys, marker="o", label=LABELS[c], color=COLORS[c])

    ax.set_xlabel("Crop price (% of baseline)")
    ax.set_ylabel("Payback period (years)")
    ax.set_title("Payback sensitivity to crop prices")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(outdir / "fig_econ_price_payback.png", dpi=140)

    plt.close(fig)


def fig_econ_discount(df, areas, prices, econ, outdir):
    rates = [0.03, 0.05, 0.07, 0.09, 0.12]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))

    for c in DEPLOYABLE:
        ys = [economics(df, c, areas, prices, econ, discount=r)[1] / 1000.0 for r in rates]
        ax.plot([int(r * 100) for r in rates], ys, marker="o", label=LABELS[c], color=COLORS[c])

    ax.axhline(0, color="#555", lw=0.8)
    ax.set_xlabel("Discount rate (%)")
    ax.set_ylabel("NPV (AUD thousands)")
    ax.set_title("NPV sensitivity to discount rate")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(outdir / "fig_econ_discount_npv.png", dpi=140)

    plt.close(fig)


def fig_econ_severeprob(df, areas, prices, econ, outdir):
    ps = [0.0, 0.1, 0.2, 0.3, 0.4]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))

    for c in DEPLOYABLE:
        ys = []

        for p in ps:
            pb, _ = economics(df, c, areas, prices, econ, p_sev=p)
            ys.append(pb if pb is not None else float("nan"))
        ax.plot([int(p * 100) for p in ps], ys, marker="o", label=LABELS[c], color=COLORS[c])

    ax.set_xlabel("Severe-year probability (%)")
    ax.set_ylabel("Payback period (years)")
    ax.set_title("Payback sensitivity to drought frequency")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(outdir / "fig_econ_severeprob_payback.png", dpi=140)

    plt.close(fig)


def summary(df, areas, prices, econ) -> dict:
    out: dict = {"design_reserve_ml": DESIGN_ML, "capex_aud": capex(econ, len(areas))}

    # severity table at 20ML
    sev = {}

    for y in [s for s in SEVERITY_ORDER if s in df.year.unique()]:
        rows = df[(df.year == y) & (df.reserve_ml == DESIGN_ML)].sort_values("production_t", ascending=False)
        best = rows.iloc[0]

        sev[y] = {
            "best_controller": best.controller,
            "best_production_t": round(float(best.production_t), 1),
            "best_saved_t": round(float(best.saved_t), 1),
            "rainfed_t": round(float(cell(df, y, "rainfed").production_t), 1),
            "mpc_t": round(float(cell(df, y, "mpc").production_t), 1),
        }

    out["severity"] = sev

    # reserve sweep for MPC severe
    mpc_sev = df[(df.year == "severe") & (df.controller == "mpc")].sort_values("reserve_ml")

    out["reserve_sweep_mpc_severe"] = {int(r.reserve_ml): round(float(r.production_t), 1) for _, r in mpc_sev.iterrows()}

    # economics base + ranges
    econ_rows = {}

    for c in DEPLOYABLE:
        pb, npv = economics(df, c, areas, prices, econ)
        pb_lo, _ = economics(df, c, areas, prices, econ, price_scale=0.8)
        pb_hi, _ = economics(df, c, areas, prices, econ, price_scale=1.2)
        _, npv_d12 = economics(df, c, areas, prices, econ, discount=0.12)

        econ_rows[c] = {
            "payback_years": round(pb, 2) if pb else None,
            "npv_aud": round(npv, 0),
            "payback_price_minus20": round(pb_lo, 2) if pb_lo else None,
            "payback_price_plus20": round(pb_hi, 2) if pb_hi else None,
            "npv_at_disc12": round(npv_d12, 0),
        }
    out["economics"] = econ_rows

    return out


def main() -> int:
    df, areas, prices, econ = load()
    outdir = REPO_ROOT / "docs" / "diagrams" / "study"
    outdir.mkdir(parents=True, exist_ok=True)

    fig_reserve_production(df, outdir)
    fig_reserve_survival(df, outdir)
    fig_severity_production(df, outdir)
    fig_econ_price(df, areas, prices, econ, outdir)
    fig_econ_discount(df, areas, prices, econ, outdir)
    fig_econ_severeprob(df, areas, prices, econ, outdir)

    s = summary(df, areas, prices, econ)
    (outdir / "study_summary.json").write_text(json.dumps(s, indent=2))

    print(f"Figures and summary written to {outdir}")
    print(json.dumps(s, indent=2))
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
