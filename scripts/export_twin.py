"""Export real engine runs to a compact JSON payload for the 2D farm twin viewer.

Runs the closed-loop engine for a set of controllers over the normal and severe 2000 season and records, per day, each field's water stress (Ks), root-zone depletion, growth stage, irrigation and a running relative yield, plus the shared reserve level and its in/out flows and the day's weather.
Data are stored as column arrays (small JSON) and, by default, injected into a self-contained HTML viewer (viz/farm_twin.html).

Usage:
    python scripts/export_twin.py           # writes viz/farm_twin.html (data embedded)
    python scripts/export_twin.py --json     # also write viz/twin_data.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.config.schema import GrowthStage
from aquareserve.controllers import (  
    MPCController,
    OracleController,
    RainfedController,
    SmartCriticalStageController,
    StochasticMPCController,
    ThresholdController,
)

# noqa: E402
from aquareserve.metrics import compute_metrics  
from aquareserve.models import YieldAccumulator, taw_from_soil  
from aquareserve.rl import LinearPolicyController  
from aquareserve.simulation import SimulationEngine  
from aquareserve.weather import columns as C  
from aquareserve.weather import load_weather  

PLANTING = "2000-05-01"
STAGE_IDX = {s: i for i, s in enumerate(GrowthStage)}


def _controllers(sc, wx):
    return [
        ("rainfed", RainfedController()),
        ("threshold", ThresholdController()),
        ("smart_rule", SmartCriticalStageController()),
        ("mpc", MPCController(sc)),
        ("stochastic_mpc", StochasticMPCController(sc)),
        ("rl_cem", LinearPolicyController.pretrained(sc)),
        ("oracle", OracleController(sc, wx, PLANTING)),
    ]


def _round(x, n):
    return round(float(x), n)


def _run_payload(sc, wx, controller, rainfed=None):
    res = SimulationEngine(sc, wx, planting_date=PLANTING).run(controller)
    metrics = compute_metrics(res, sc)
    zd = res.zone_days.reset_index()
    zones = {z.id: z for z in sc.farm.zones}
    crops = {zid: sc.crops[z.crop] for zid, z in zones.items()}
    taw = {zid: taw_from_soil(z.soil.total_available_water_mm_per_m, crops[zid].root_depth.max_m) for zid, z in zones.items()}
    season = {zid: crops[zid].stage_days.total for zid in zones}

    # Play a week past the longest-season crop so every field, including the last to mature, visibly reaches its Harvested state on the timeline.
    n_days = max(season.values()) + 7

    zones_out = {}

    for zid in zones:
        sub = zd[zd["zone_id"] == zid].sort_values("date")
        acc = YieldAccumulator(crops[zid])
        ks, depl, irr, yld, stg, growth = [], [], [], [], [], []

        for i in range(n_days):

            if i < len(sub):
                row = sub.iloc[i]
                stage = GrowthStage(row["stage"])
                acc.add_day(stage, row["etc_mm"], row["eta_mm"])
                ks.append(_round(row["ks"], 3))
                depl.append(_round(min(1.5, row["depletion_mm"] / taw[zid]), 3))
                irr.append(_round(row["irrig_mm"], 2))
                yld.append(_round(acc.result().relative_yield, 3))
                stg.append(STAGE_IDX[stage])
                growth.append(_round(min(1.0, (i + 1) / season[zid]), 3))
                
            # after harvest
            else: 
                ks.append(None)
                depl.append(None)
                irr.append(0.0)
                yld.append(yld[-1] if yld else 0.0)
                stg.append(3)
                growth.append(1.0)

        zm = next(m for m in metrics.zones if m.zone_id == zid)

        zones_out[zid] = {
            "ks": ks, "depl": depl, "irr": irr, "yield": yld, "stage": stg, "growth": growth,
            "final_yield_t_ha": _round(zm.yield_t_ha, 2),
            "production_t": _round(zm.production_t, 1),
            "rel_yield": _round(zm.relative_yield, 3),
            "harvest_day": season[zid],
            "rainfed_final_t_ha": (rainfed or {}).get(zid, 0.0),
        }

    rv = res.reserve.reset_index()

    def _pad(vals, fill):
        vals = list(vals)
        return vals + [fill] * (n_days - len(vals))

    last_vol = _round(rv["volume_m3"].iloc[-1] / 1000.0, 2) if len(rv) else 0.0
    last_frac = _round(rv["fraction_full"].iloc[-1], 3) if len(rv) else 0.0

    reserve = {
        "vol_ml": _pad([_round(v / 1000.0, 2) for v in rv["volume_m3"]], last_vol),
        "frac": _pad([_round(f, 3) for f in rv["fraction_full"]], last_frac),
        "withdraw_m3": _pad([_round(w, 0) for w in rv["withdrawal_m3"]], 0.0),
        "capture_m3": _pad([_round(c, 0) for c in rv["capture_m3"]], 0.0),
        "spill_m3": _pad([_round(s, 0) for s in rv["spill_m3"]], 0.0),
    }

    win = wx.loc[PLANTING:].iloc[:n_days]

    weather = {"rain": [_round(r, 1) for r in win[C.RAIN]], "et0": [_round(e, 1) for e in win[C.ET0]]}
    dates = [d.strftime("%Y-%m-%d") for d in win.index[:n_days]]

    return {
        "days": n_days,
        "dates": dates,
        "zones": zones_out,
        "reserve": reserve,
        "weather": weather,
        "summary": {
            "production_t": _round(metrics.total_production_t, 1),
            "rainfed_production_t": (rainfed or {}).get("__total__", 0.0),
            "irrigation_ml": _round(metrics.total_irrigation_m3 / 1000.0, 2),
            "reserve_survival_days": int(metrics.reserve_survival_days),
            "value_aud": _round(sum(
                next(m for m in metrics.zones if m.zone_id == zid).production_t
                * crops[zid].price_per_t for zid in zones), 0),
        },
    }


def build_payload():
    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    zones = sc.farm.zones

    # Equal-width strip layout in normalised [0,1] coordinates (gaps between fields).
    # Fields are drawn the same size for legibility; the hectares are shown on each label.
    gap, x = 0.02, 0.0
    layout = []
    n = len(zones)
    w = (1.0 - gap * (n - 1)) / n

    for z in zones:
        crop = sc.crops[z.crop]
        method = "drip" if z.irrigation_efficiency >= 0.85 else "broadacre"
        layout.append({"id": z.id, "label": crop.display_name, "crop": z.crop, 
                       "area_ha": z.area_ha, "method": method,
                       "ref_yield_t_ha": _round(crop.reference_yield_t_per_ha, 2),
                       "x": _round(x, 4), "w": _round(w, 4)})
        x += w + gap

    meta = {
        "farm": sc.farm.name,
        "region": sc.climate.region,
        "planting": PLANTING,
        "capacity_ml": _round(sc.farm.reserve.capacity_m3 / 1000.0, 1),
        "zones": layout,
        "stages": [s.value for s in GrowthStage],
        "controllers": ["rainfed", "threshold", "smart_rule", "mpc",
                        "stochastic_mpc", "rl_cem", "oracle"],
        "controller_labels": {
            "rainfed": "Rainfed (no irrigation)", "threshold": "Soil-moisture threshold",
            "smart_rule": "Smart critical-stage", "mpc": "MPC (model predictive)",
            "stochastic_mpc": "Robust MPC (ensemble)", "rl_cem": "RL policy (learned)",
            "oracle": "Oracle (perfect foresight)"},
        "years": ["normal", "severe"],
    }

    runs = {}

    for year in ("normal", "severe"):
        wx = load_weather(sc.climate, scenario_name=year, base_dir=str(REPO_ROOT))

        # rainfed (no-irrigation) baseline for this season: the "do nothing" outcome the irrigation system is measured against, per field and in total.
        rf = compute_metrics(SimulationEngine(sc, wx, planting_date=PLANTING).run(RainfedController()), sc)
        rainfed = {zm.zone_id: _round(zm.yield_t_ha, 2) for zm in rf.zones}
        rainfed["__total__"] = _round(rf.total_production_t, 1)

        for name, _ in _controllers(sc, wx):
            ctrl = dict(_controllers(sc, wx))[name]
            runs[f"{name}|{year}"] = _run_payload(sc, wx, ctrl, rainfed)

    return {"meta": meta, "runs": runs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="also write viz/twin_data.json")

    args = ap.parse_args()

    payload = build_payload()

    viz = REPO_ROOT / "viz"
    viz.mkdir(exist_ok=True)

    data_str = json.dumps(payload, separators=(",", ":"))

    if args.json:
        (viz / "twin_data.json").write_text(data_str)
        print(f"wrote viz/twin_data.json ({len(data_str) / 1024:.0f} KB)")

    for tpl, out in (("_template.html", "farm_twin.html"),
                     ("_template3d.html", "farm_twin_3d.html")):
        tpl_path = viz / tpl
        
        if not tpl_path.exists():
            continue

        html = tpl_path.read_text().replace("/*__TWIN_DATA__*/null", data_str)
        (viz / out).write_text(html)
        print(f"wrote viz/{out} ({len(html) / 1024:.0f} KB, data {len(data_str) / 1024:.0f} KB)")
        
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
