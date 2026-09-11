"""Command-line entry point for AquaReserve.

Currently exposes a ``validate`` command that loads and checks a scenario.
Simulation/run commands are added in later phases.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_scenario
from .units import m3_to_ml

# Repo-relative default scenario
DEFAULT_FARM = "config/farm.example.yaml"


def _print_summary(farm_path: str) -> int:
    try:
        scenario = load_scenario(farm_path)
    
    # surface a clean message
    except Exception as exc:  

        print(f"[INVALID] {farm_path}\n  {type(exc).__name__}: {exc}", file=sys.stderr)

        return 1

    farm = scenario.farm
    reserve = farm.reserve

    # guaranteed by scenario validation
    assert reserve is not None  

    print(f"[OK] Scenario loaded: {farm.name}")

    print(f"  Region        : {farm.location.region} "
          f"({farm.location.latitude:.2f}, {farm.location.longitude:.2f})")

    print(f"  Total area    : {scenario.total_area_ha:.1f} ha across {len(farm.zones)} zone(s)")

    print(f"  Reserve       : {reserve.initial_volume_m3:,.0f} / {reserve.capacity_m3:,.0f} m3 "
          f"({m3_to_ml(reserve.capacity_m3):.1f} ML capacity)")

    print(f"  Climate       : {scenario.climate.region} "
          f"[{scenario.climate.dataset.source.value}]")

    print(f"  Drought scen. : {', '.join(s.name for s in scenario.climate.drought_scenarios) or 'none'}")

    print("  Zones:")

    for z in farm.zones:
        crop = scenario.crops[z.crop]

        print(f"    - {z.id:<10} {crop.display_name:<8} {z.area_ha:>5.1f} ha  "
              f"{z.irrigation_system.value:<18} strategy={z.strategy.value}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aquareserve",
        description="Smart supplementary irrigation digital twin.",
    )
    
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="load and validate a scenario config")
    p_validate.add_argument(
        "farm",
        nargs="?",
        default=DEFAULT_FARM,
        help=f"path to a farm config YAML (default: {DEFAULT_FARM})",
    )

    args = parser.parse_args(argv)

    if args.command == "validate":

        # Resolve relative to CWD; fall back to repo root if run from elsewhere.
        farm_path = args.farm

        if not Path(farm_path).exists():
            repo_root = Path(__file__).resolve().parents[2]
            candidate = repo_root / farm_path

            if candidate.exists():
                farm_path = str(candidate)

        return _print_summary(farm_path)

    parser.error(f"unknown command: {args.command}")
    
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
