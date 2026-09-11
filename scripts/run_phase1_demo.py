"""Rainfed-season demonstration: one rainfed season, normal vs severe drought.

Runs the open-loop water pipeline - weather -> crop demand (Kc x ET0) -> root-zone soil-water balance -> stress -> FAO-33 yield - for a single zone with no irrigation, under the 'normal' and 'severe' climate scenarios.
Prints a season summary (including yield) and saves a three-panel figure.

Usage:
    python scripts/run_phase1_demo.py            # wheat-1, plant 2015-05-01
    python scripts/run_phase1_demo.py onion-1    # a different zone

Open-loop demo (rainfed, no reserve/controller yet).
Root depth is held at the crop maximum; dynamic root growth and irrigation arrive in later phases.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Allow running from a source checkout without installing.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.config.schema import GrowthStage  
from aquareserve.models import (  
    CropCurve,
    SoilWaterBalance,
    YieldAccumulator,
    taw_from_soil,
)
from aquareserve.weather import columns as C  
from aquareserve.weather import load_weather  

# real SILO year available in data/raw/silo_mildura.txt
PLANTING_DATE = "2000-05-01"  


def run_season(zone, crop, weather: pd.DataFrame) -> pd.DataFrame:

    """Run a rainfed soil-water balance over one season; return a per-day DataFrame."""
    curve = CropCurve(crop)
    taw = taw_from_soil(zone.soil.total_available_water_mm_per_m, crop.root_depth.max_m)

    swb = SoilWaterBalance(
        taw_mm=taw,
        depletion_fraction_p=crop.depletion_fraction_p,
        initial_depletion_mm=zone.soil.initial_depletion_fraction * taw,
    )

    start = pd.Timestamp(PLANTING_DATE)
    season = weather.loc[start : start + pd.Timedelta(days=crop.stage_days.total - 1)]

    rows = []

    for day, (date, wx) in enumerate(season.iterrows()):
        etc = curve.crop_demand_mm(day, wx[C.ET0])
        step = swb.step(rain_mm=wx[C.RAIN], crop_et_mm=etc, irrigation_mm=0.0)

        rows.append(
            {
                "date": date,
                "day": day,
                "stage": curve.stage(day).value,
                "rain_mm": wx[C.RAIN],
                "et0_mm": wx[C.ET0],
                "kc": curve.kc(day),
                "etc_mm": etc,
                "eta_mm": step.actual_et_mm,
                "depletion_mm": step.depletion_mm,
                "ks": step.stress_coefficient,
                "raw_mm": swb.raw_mm,
                "taw_mm": swb.taw,
            }
        )

    return pd.DataFrame(rows).set_index("date")


def compute_yield(crop, df: pd.DataFrame):

    """Accumulate stage ET from a season DataFrame and return a FAO-33 YieldResult."""
    acc = YieldAccumulator(crop)

    for _, row in df.iterrows():
        acc.add_day(GrowthStage(row["stage"]), row["etc_mm"], row["eta_mm"])

    return acc.result()


def summarise(name: str, df: pd.DataFrame, crop) -> None:

    stress_days = int((df["ks"] < 0.999).sum())
    y = compute_yield(crop, df)

    print(
        f"  [{name:7s}] rain={df['rain_mm'].sum():6.1f}mm  "
        f"ETc={df['etc_mm'].sum():6.1f}mm  ETa={df['eta_mm'].sum():6.1f}mm  "
        f"deficit={df['etc_mm'].sum() - df['eta_mm'].sum():6.1f}mm  "
        f"stress-days={stress_days:3d}  "
        f"rel_yield={y.relative_yield:4.0%}  yield={y.actual_yield_t_ha:4.1f} t/ha"
    )


def plot(zone_id: str, crop_name: str, normal: pd.DataFrame, severe: pd.DataFrame, out: Path) -> None:

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

    except ImportError:
        print("  (matplotlib not installed - skipping plot; `pip install matplotlib`)")

        return

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    fig.suptitle(
        f"AquaReserve - rainfed {crop_name} season ({zone_id}), normal vs severe drought",
        fontsize=13, fontweight="bold",
    )

    ax1.bar(severe.index, severe["rain_mm"], width=1.0, color="#4a90d9", alpha=0.6, label="rain (severe)")
    ax1.plot(severe.index, severe["etc_mm"], color="#c0392b", lw=1.3, label="crop demand ET_c")
    ax1.plot(severe.index, severe["eta_mm"], color="#27ae60", lw=1.3, label="actual ET_a (severe)")
    ax1.set_ylabel("mm/day")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.set_title("Water supply & demand", fontsize=10, loc="left")

    ax2.plot(normal.index, normal["depletion_mm"], color="#2980b9", lw=1.6, label="depletion (normal)")
    ax2.plot(severe.index, severe["depletion_mm"], color="#c0392b", lw=1.6, label="depletion (severe)")
    ax2.axhline(severe["raw_mm"].iloc[0], color="#e67e22", ls="--", lw=1, label="RAW (stress onset)")
    ax2.axhline(severe["taw_mm"].iloc[0], color="#7f8c8d", ls=":", lw=1, label="TAW (wilting)")
    ax2.fill_between(severe.index, severe["raw_mm"].iloc[0], severe["taw_mm"].iloc[0], color="#e74c3c", alpha=0.06)
    ax2.set_ylabel("root-zone depletion (mm)")
    ax2.set_title("Root-zone depletion vs stress thresholds", fontsize=10, loc="left")

    # The y-axis is inverted, so every in-axes corner sits on the curves or the
    # thresholds. Put the key on the title line instead, clear of the data.
    ax2.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4, fontsize=8, frameon=False, borderaxespad=0.0)

    # more depleted = drier = lower
    ax2.invert_yaxis()  

    ax3.plot(normal.index, normal["ks"], color="#2980b9", lw=1.6, label="Ks (normal)")
    ax3.plot(severe.index, severe["ks"], color="#c0392b", lw=1.6, label="Ks (severe)")
    ax3.set_ylabel("stress coeff. Ks")
    ax3.set_ylim(0, 1.05)
    ax3.legend(loc="lower left", fontsize=8)
    ax3.set_title("Water-stress coefficient (1 = unstressed, 0 = wilting)", fontsize=10, loc="left")

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)

    print(f"  figure saved -> {out}")


def main(zone_id: str = "wheat-1") -> int:

    scenario = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    zone = next((z for z in scenario.farm.zones if z.id == zone_id), None)

    if zone is None:
        print(f"zone '{zone_id}' not found; available: "
              f"{', '.join(z.id for z in scenario.farm.zones)}")

        return 1

    crop = scenario.crops[zone.crop]

    normal_wx = load_weather(scenario.climate, scenario_name="normal", seed=2015)
    severe_wx = load_weather(scenario.climate, scenario_name="severe", seed=2015)

    normal = run_season(zone, crop, normal_wx)
    severe = run_season(zone, crop, severe_wx)

    print(f"AquaReserve demo - {crop.display_name} ({zone_id}), sown {PLANTING_DATE}")
    print(f"  TAW={severe['taw_mm'].iloc[0]:.0f}mm  RAW={severe['raw_mm'].iloc[0]:.0f}mm  "
          f"season={crop.stage_days.total} days  ref_yield={crop.reference_yield_t_per_ha} t/ha")

    summarise("normal", normal, crop)
    summarise("severe", severe, crop)

    y_norm = compute_yield(crop, normal).actual_yield_t_ha
    y_sev = compute_yield(crop, severe).actual_yield_t_ha

    print(f"  => rainfed yield lost to severe drought: {y_norm - y_sev:.1f} t/ha "
          f"({(y_norm - y_sev) / max(y_norm, 1e-9):.0%})")

    plot(zone_id, crop.display_name, normal, severe,
         REPO_ROOT / "outputs" / f"phase1_{zone_id}_season.png")
         
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "wheat-1"))
