"""Experiment matrix runner.

Precomputes the scenario x controller x reserve-size matrix once and writes it to a results store, so the dashboard serves results without ever running the engine live.
Each cell records the season outcome (production, irrigation, reserve survival, farmgate value) plus the amount saved over the rainfed (no-system) baseline and the per-crop yield.

The store is written as CSV (always), plus Parquet and a DuckDB database when duckdb is available (it is in the `api` extra).
DuckDB writes Parquet natively, so pyarrow is optional.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config.schema import Scenario

from ..controllers import (
    MPCController,
    OracleController,
    RainfedController,
    SmartCriticalStageController,
    StochasticMPCController,
    ThresholdController,
)

from ..metrics import compute_metrics
from ..rl import LinearPolicyController
from ..simulation import SimulationEngine
from ..weather import load_weather

# name -> factory(resized_scenario, weather, planting) so controllers that hold the scenario (MPC, robust MPC, oracle, RL) are rebuilt for each reserve size.
CONTROLLERS = {
    "rainfed": lambda sc, wx, pl: RainfedController(),
    "threshold": lambda sc, wx, pl: ThresholdController(),
    "smart_rule": lambda sc, wx, pl: SmartCriticalStageController(),
    "mpc": lambda sc, wx, pl: MPCController(sc),
    "stochastic_mpc": lambda sc, wx, pl: StochasticMPCController(sc),
    "rl_cem": lambda sc, wx, pl: LinearPolicyController.pretrained(sc),
    "oracle": lambda sc, wx, pl: OracleController(sc, wx, pl),
}

DEFAULT_RESERVE_SIZES_ML = [5, 10, 15, 20, 25, 30, 40]


def resize_reserve(scenario: Scenario, capacity_ml: float) -> Scenario:
    """Return a deep copy of the scenario with the reserve resized to ``capacity_ml``, holding the season-start fill fraction constant so sizes compare fairly.
    """
    frac = scenario.farm.reserve.initial_volume_m3 / scenario.farm.reserve.capacity_m3

    sc = scenario.model_copy(deep=True)
    sc.farm.reserve.capacity_m3 = capacity_ml * 1000.0
    sc.farm.reserve.initial_volume_m3 = frac * capacity_ml * 1000.0

    return sc


def run_matrix(scenario: Scenario, years, controllers=None, reserve_sizes_ml=None, planting: str = "2000-05-01", base_dir: str = ".") -> pd.DataFrame: 
    """Run every (year x controller x reserve-size) cell and return a tidy DataFrame."""
    controllers = controllers or CONTROLLERS
    reserve_sizes_ml = reserve_sizes_ml or DEFAULT_RESERVE_SIZES_ML
    crop_of = {z.id: z.crop for z in scenario.farm.zones}
    rows = []

    for year in years:
        wx = load_weather(scenario.climate, scenario_name=year, base_dir=base_dir)
        
        # rainfed baseline is reserve-independent (no irrigation), so compute once per year
        rf = compute_metrics(
            SimulationEngine(scenario, wx, planting_date=planting).run(RainfedController()),
            scenario,
        ).total_production_t

        for cap_ml in reserve_sizes_ml:
            sc = resize_reserve(scenario, cap_ml)
            engine = SimulationEngine(sc, wx, planting_date=planting)
            zone_by_id = {z.id: z for z in sc.farm.zones}

            for name, factory in controllers.items():
                m = compute_metrics(engine.run(factory(sc, wx, planting)), sc)
                value = sum(z.production_t * sc.crops[zone_by_id[z.zone_id].crop].price_per_t for z in m.zones)
                saved = m.total_production_t - rf

                row = {
                    "year": year,
                    "controller": name,
                    "reserve_ml": float(cap_ml),
                    "production_t": round(m.total_production_t, 2),
                    "irrigation_ml": round(m.total_irrigation_m3 / 1000.0, 3),
                    "survival_days": int(m.reserve_survival_days),
                    "value_aud": round(value, 0),
                    "rainfed_t": round(rf, 2),
                    "saved_t": round(saved, 2),
                    "saved_pct": round(100.0 * saved / rf, 1) if rf > 0 else 0.0,
                }

                for z in m.zones:
                    row[f"{crop_of[z.zone_id]}_t_ha"] = round(z.yield_t_ha, 2)

                rows.append(row)
                
    return pd.DataFrame(rows)


def write_results(df: pd.DataFrame, out_dir: str | Path) -> list[Path]:
    """Write the matrix to CSV (always) plus Parquet and DuckDB when duckdb is available."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv = out / "matrix.csv"
    df.to_csv(csv, index=False)
    written = [csv]

    try:
        import duckdb

        con = duckdb.connect(str(out / "aquareserve.duckdb"))
        con.register("m", df)
        con.execute("CREATE OR REPLACE TABLE results AS SELECT * FROM m")
        con.execute(f"COPY results TO '{out / 'matrix.parquet'}' (FORMAT PARQUET)")
        con.close()
        written += [out / "matrix.parquet", out / "aquareserve.duckdb"]

    except ImportError:
        # CSV is enough; Parquet/DuckDB need the `api` extra (duckdb)
        pass  

    return written
