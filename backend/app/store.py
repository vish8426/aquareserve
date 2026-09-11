"""Read-only access to the precomputed results store and scenario config

The store is the output (``data/results/matrix.parquet`` plus a DuckDB database and a CSV).
This module queries it and derives everything the dashboard needs (metadata, controller comparison, reserve-size sensitivity, ROI) without running the engine.
The ROI figures are pure arithmetic over the matrix and the economics config, so no simulation runs at request time.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

# Repo root = .../aquareserve (this file is aquareserve/backend/app/store.py).
REPO_ROOT = Path(os.environ.get("AQUARESERVE_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = Path(os.environ.get("AQUARESERVE_DATA_DIR", REPO_ROOT / "data" / "results"))
CONFIG_DIR = Path(os.environ.get("AQUARESERVE_CONFIG_DIR", REPO_ROOT / "config"))
VIZ_DIR = Path(os.environ.get("AQUARESERVE_VIZ_DIR", REPO_ROOT / "viz"))

# Make the aquareserve core importable when running from a source checkout (not installed).
_SRC = REPO_ROOT / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

DESIGN_RESERVE_ML = 20.0  # the design reserve the farm was sized for

CONTROLLER_LABELS = {
    "rainfed": "Rainfed (no system)",
    "fixed": "Fixed schedule",
    "threshold": "Soil-moisture threshold",
    "smart_rule": "Smart critical-stage",
    "mpc": "MPC",
    "stochastic_mpc": "Robust MPC",
    "rl_cem": "RL policy (CEM)",
    "oracle": "Oracle (perfect foresight)",
}
YEAR_LABELS = {
    "normal": "Normal (real 2000)",
    "moderate": "Moderate drought",
    "severe": "Severe drought (real 2019)",
}
# Controllers that model a live decision (exclude the no-system baseline and the unrealisable perfect-foresight oracle) - used to rank "deployable" options in ROI.
DEPLOYABLE = {"threshold", "smart_rule", "mpc", "stochastic_mpc", "rl_cem"}


class StoreError(RuntimeError):
    """Raised when the results store is missing or unreadable."""


def _load_matrix() -> list[dict[str, Any]]:
    """Load the results matrix as a list of plain dicts.
    Prefers Parquet via DuckDB, and falls back to the CSV so the API still works without the optional data stack.
    """
    parquet = DATA_DIR / "matrix.parquet"
    csv = DATA_DIR / "matrix.csv"
    if parquet.exists():
        try:
            import duckdb

            rows = duckdb.query(
                f"SELECT * FROM read_parquet('{parquet.as_posix()}')"
            ).fetchall()
            cols = [d[0] for d in duckdb.query(
                f"SELECT * FROM read_parquet('{parquet.as_posix()}') LIMIT 0"
            ).description]
            return [dict(zip(cols, r, strict=True)) for r in rows]
        except Exception:  # noqa: BLE001 - fall back to CSV on any DuckDB issue
            pass
    if csv.exists():
        import csv as csvmod

        with csv.open(newline="") as fh:
            out: list[dict[str, Any]] = []
            for r in csvmod.DictReader(fh):
                row: dict[str, Any] = {}
                for k, v in r.items():
                    try:
                        row[k] = float(v) if v not in ("", None) else None
                    except (TypeError, ValueError):
                        row[k] = v
                out.append(row)
            return out
    raise StoreError(
        f"No results store found in {DATA_DIR}. Run 'python scripts/run_matrix.py' first."
    )


class ResultsStore:
    """Loads the matrix and scenario once and answers dashboard queries over them."""

    def __init__(self) -> None:
        self.rows = _load_matrix()
        for r in self.rows:  # normalise numeric types the CSV path leaves as float
            r["reserve_ml"] = float(r["reserve_ml"])
            r["survival_days"] = int(r["survival_days"]) if r.get("survival_days") is not None else 0
        self._load_config()

    def _load_config(self) -> None:
        from aquareserve.config import load_scenario
        from aquareserve.config.loader import load_economics

        self.scenario = load_scenario(CONFIG_DIR / "farm.example.yaml")
        self.econ = load_economics(CONFIG_DIR / "economics.example.yaml")
        self.zones = [
            {
                "id": z.id,
                "crop": z.crop,
                "area_ha": z.area_ha,
                "irrigation_system": z.irrigation_system,
                "horticulture": z.irrigation_system == "drip",
                "price_per_t": self.scenario.crops[z.crop].price_per_t,
            }
            for z in self.scenario.farm.zones
        ]

    # -- lookups ---------------------------------------------------------------
    @property
    def years(self) -> list[str]:
        return sorted({r["year"] for r in self.rows}, key=lambda y: 0 if y == "normal" else 1)

    @property
    def controllers(self) -> list[str]:
        order = list(CONTROLLER_LABELS)
        found = {r["controller"] for r in self.rows}
        return [c for c in order if c in found]

    @property
    def reserve_sizes(self) -> list[float]:
        return sorted({r["reserve_ml"] for r in self.rows})

    def meta(self) -> dict[str, Any]:
        return {
            "farm": self.scenario.farm.name,
            "region": self.scenario.farm.location.region,
            "reserve_capacity_ml": self.scenario.farm.reserve.capacity_m3 / 1000.0,
            "design_reserve_ml": DESIGN_RESERVE_ML,
            "currency": self.econ.currency,
            "zones": self.zones,
            "controllers": [
                {"id": c, "label": CONTROLLER_LABELS.get(c, c), "deployable": c in DEPLOYABLE}
                for c in self.controllers
            ],
            "years": [{"id": y, "label": YEAR_LABELS.get(y, y)} for y in self.years],
            "reserve_sizes_ml": self.reserve_sizes,
        }

    def matrix(self, year: str | None = None, controller: str | None = None,
               reserve_ml: float | None = None) -> list[dict[str, Any]]:
        out = self.rows
        if year is not None:
            out = [r for r in out if r["year"] == year]
        if controller is not None:
            out = [r for r in out if r["controller"] == controller]
        if reserve_ml is not None:
            out = [r for r in out if r["reserve_ml"] == reserve_ml]
        return out

    def comparison(self, year: str, reserve_ml: float = DESIGN_RESERVE_ML) -> list[dict[str, Any]]:
        rows = self.matrix(year=year, reserve_ml=reserve_ml)
        if not rows:
            raise StoreError(f"No rows for year={year} reserve_ml={reserve_ml}")
        rows = sorted(rows, key=lambda r: r["production_t"], reverse=True)
        for r in rows:
            r["label"] = CONTROLLER_LABELS.get(r["controller"], r["controller"])
        return rows

    def reserve_sweep(self, controller: str, year: str) -> list[dict[str, Any]]:
        rows = self.matrix(year=year, controller=controller)
        if not rows:
            raise StoreError(f"No rows for controller={controller} year={year}")
        return sorted(rows, key=lambda r: r["reserve_ml"])

    def roi(self, reserve_ml: float = DESIGN_RESERVE_ML) -> dict[str, Any]:
        """Economics per controller at the design reserve: capex, expected annual benefit, payback and NPV. 
        Uses the matrix farmgate values and the economics config only."""
        econ = self.econ
        p = econ.severe_year_probability
        r = econ.discount_rate

        def value(controller: str, year: str) -> float:
            rows = self.matrix(year=year, controller=controller, reserve_ml=reserve_ml)
            return float(rows[0]["value_aud"]) if rows else 0.0

        # capex scales with the reserve build cost at this size
        storage = reserve_ml * 1000.0 * econ.costs.storage_capex_per_m3
        hardware = len(self.zones) * econ.costs.per_zone_hardware + econ.costs.gateway
        capex = storage + hardware + econ.costs.install

        rainfed_norm = value("rainfed", "normal")
        rainfed_sev = value("rainfed", "severe")
        results = []
        for c in self.controllers:
            if c == "rainfed":
                continue
            b_norm = value(c, "normal") - rainfed_norm - econ.costs.annual_opex - econ.costs.subscription_per_year
            b_sev = value(c, "severe") - rainfed_sev - econ.costs.annual_opex - econ.costs.subscription_per_year
            expected = (1 - p) * b_norm + p * b_sev
            npv = -capex + sum(expected / (1 + r) ** y for y in range(1, econ.horizon_years + 1))
            payback = capex / expected if expected > 0 else None
            results.append({
                "controller": c,
                "label": CONTROLLER_LABELS.get(c, c),
                "deployable": c in DEPLOYABLE,
                "annual_benefit_normal": round(b_norm, 0),
                "annual_benefit_severe": round(b_sev, 0),
                "expected_annual_benefit": round(expected, 0),
                "payback_years": round(payback, 2) if payback is not None else None,
                "npv": round(npv, 0),
            })
        results.sort(key=lambda x: x["npv"], reverse=True)
        return {
            "reserve_ml": reserve_ml,
            "capex": round(capex, 0),
            "currency": econ.currency,
            "discount_rate": r,
            "horizon_years": econ.horizon_years,
            "severe_year_probability": p,
            "controllers": results,
        }

    def twin_data_path(self) -> Path | None:
        p = VIZ_DIR / "twin_data.json"
        return p if p.exists() else None


@lru_cache(maxsize=1)
def get_store() -> ResultsStore:
    """Process-wide singleton so the matrix and config load once."""
    return ResultsStore()
