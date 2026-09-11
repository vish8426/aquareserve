"""Precompute the scenario x controller x reserve-size results matrix.

Runs the engine across every year, controller and reserve size and writes the outcome to a results store (CSV always; Parquet + DuckDB when duckdb is installed).
This is the precompute and serve step: the dashboard reads this store instead of running the engine live.

Usage:
    python scripts/run_matrix.py [--out data/results] [--reserves 5 10 15 20 25 30 40]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# noqa: E402
from aquareserve.config import load_scenario  
from aquareserve.experiments import (  
    DEFAULT_RESERVE_SIZES_ML,
    run_matrix,
    write_results,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/results", help="output directory for the results store")
    ap.add_argument("--reserves", type=float, nargs="+", default=DEFAULT_RESERVE_SIZES_ML, help="reserve sizes in ML to sweep")
    ap.add_argument("--years", nargs="+", default=["normal", "severe"], help="climate scenarios")
    args = ap.parse_args()

    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")

    print(f"Running matrix: {len(args.years)} years x 7 controllers x {len(args.reserves)} "
          f"reserve sizes = {len(args.years) * 7 * len(args.reserves)} cells ...")

    df = run_matrix(sc, years=args.years, reserve_sizes_ml=args.reserves, base_dir=str(REPO_ROOT))
    written = write_results(df, REPO_ROOT / args.out)

    print(f"{len(df)} rows written to:")

    for p in written:
        print(f"  {p}")

    # quick headline: production at the 20 ML design point
    base = df[df["reserve_ml"] == 20.0]

    if not base.empty:
        print("\nAt the 20 ML design reserve:")

        for year in args.years:
            sub = base[base["year"] == year].sort_values("production_t")
            best = sub.iloc[-1]
            print(f"  {year:7s}: best {best['controller']} {best['production_t']:.0f} t "
                  f"(saved +{best['saved_t']:.0f} t vs rainfed)")
                  
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
