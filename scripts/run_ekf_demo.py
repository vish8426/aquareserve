"""Estimator demo: EKF vs EnKF recovering true root-zone water from a noisy probe.

Runs a real wheat season, simulates a noisy soil-moisture probe read every few days and compares the Extended Kalman Filter and the Ensemble Kalman Filter at recovering the true root-zone depletion.
Both fuse the sensor with the soil-water-balance model.
Saves a figure and prints the error reduction for each.

Usage:
    python scripts/run_ekf_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.estimation import RootZoneEKF, RootZoneEnKF  
from aquareserve.models import CropCurve, SoilWaterBalance, taw_from_soil  
from aquareserve.weather import columns as C  
from aquareserve.weather import load_weather  

PLANTING = "2000-05-01"
NOISE_SD = 20.0
MEAS_EVERY = 3
ENSEMBLE = 60


def main() -> int:
    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    zone = next(z for z in sc.farm.zones if z.id == "wheat-1")
    crop = sc.crops["wheat"]
    wx = load_weather(sc.climate, scenario_name="severe", base_dir=str(REPO_ROOT))
    start = pd.Timestamp(PLANTING)
    season = wx.loc[start : start + pd.Timedelta(days=crop.stage_days.total - 1)]

    taw = taw_from_soil(zone.soil.total_available_water_mm_per_m, crop.root_depth.max_m)
    p = crop.depletion_fraction_p
    d0 = zone.soil.initial_depletion_fraction * taw
    curve = CropCurve(crop)
    truth = SoilWaterBalance(taw, p, d0)
    ekf = RootZoneEKF(taw, p, d0, measurement_variance=NOISE_SD**2)
    enkf = RootZoneEnKF(taw, p, d0, measurement_variance=NOISE_SD**2, ensemble_size=ENSEMBLE, seed=0)
    rng = np.random.default_rng(0)

    dates, true_dr, sensor_dr, ekf_dr, enkf_dr = [], [], [], [], []

    for day, (dt, r) in enumerate(season.iterrows()):
        etc = curve.crop_demand_mm(day, r[C.ET0])
        step = truth.step(rain_mm=r[C.RAIN], crop_et_mm=etc)
        ekf.predict(rain_mm=r[C.RAIN], crop_et_mm=etc)
        enkf.predict(rain_mm=r[C.RAIN], crop_et_mm=etc)
        z = np.nan

        if day % MEAS_EVERY == 0:
            z = step.depletion_mm + rng.normal(0, NOISE_SD)
            ekf.update(z)
            enkf.update(z)

        dates.append(dt)
        true_dr.append(step.depletion_mm)
        sensor_dr.append(z)
        ekf_dr.append(ekf.depletion_mm)
        enkf_dr.append(enkf.depletion_mm)

    true_dr = np.array(true_dr)
    sensor_dr = np.array(sensor_dr)
    ekf_dr = np.array(ekf_dr)
    enkf_dr = np.array(enkf_dr)
    mask = ~np.isnan(sensor_dr)

    def rmse(a):
        return float(np.sqrt(np.mean((a - true_dr) ** 2)))

    rmse_sensor = float(np.sqrt(np.mean((sensor_dr[mask] - true_dr[mask]) ** 2)))
    rmse_ekf, rmse_enkf = rmse(ekf_dr), rmse(enkf_dr)

    print("Root-zone estimation - EKF vs EnKF (real wheat severe-drought season)")
    print(f"  sensor reads every {MEAS_EVERY} days, noise sd {NOISE_SD} mm")
    print(f"  raw sensor RMSE : {rmse_sensor:5.1f} mm")
    print(f"  EKF  RMSE       : {rmse_ekf:5.1f} mm  (cuts error {100*(rmse_sensor-rmse_ekf)/rmse_sensor:.0f}%)")
    print(f"  EnKF RMSE       : {rmse_enkf:5.1f} mm  (cuts error {100*(rmse_sensor-rmse_enkf)/rmse_sensor:.0f}%, ensemble of {ENSEMBLE})")

    _plot(dates, true_dr, sensor_dr, ekf_dr, enkf_dr, rmse_sensor, rmse_ekf, rmse_enkf, REPO_ROOT / "outputs" / "ekf_vs_enkf.png")

    return 0


def _plot(dates, true_dr, sensor_dr, ekf_dr, enkf_dr, rmse_sensor, rmse_ekf, rmse_enkf, out: Path) -> None:

    try:
        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt

    except ImportError:

        return

    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(dates, true_dr, color="#2c3e50", lw=2, label="true depletion")
    ax.scatter(dates, sensor_dr, s=18, color="#e67e22", alpha=0.6, label=f"noisy sensor (RMSE {rmse_sensor:.1f} mm)")
    ax.plot(dates, ekf_dr, color="#27ae60", lw=1.7, ls="--", label=f"EKF (RMSE {rmse_ekf:.1f} mm)")
    ax.plot(dates, enkf_dr, color="#8e44ad", lw=1.7, ls="-.", label=f"EnKF (RMSE {rmse_enkf:.1f} mm)")
    ax.set_ylabel("root-zone depletion (mm)")
    ax.invert_yaxis()
    ax.set_title("AquaReserve - EKF vs EnKF fuse a noisy probe with the soil-water model", fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)

    fig.tight_layout()

    out.parent.mkdir(parents=True, exist_ok=True)
    
    fig.savefig(out, dpi=130)

    print(f"  figure saved -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
