"""Hardware costing from the machine-readable BOM (``config/bom.yaml``).

Keeps the configurator's capex in step with the spreadsheet and the economics model: the same per-zone, central, install and storage numbers drive all three.
Pure data plus arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LineItem:
    item: str
    type: str
    qty: float
    unit_cost: float

    @property
    def total(self) -> float:
        return self.qty * self.unit_cost

    def as_dict(self) -> dict:
        return {
            "item": self.item,
            "type": self.type,
            "qty": self.qty,
            "unit_cost": round(self.unit_cost, 2),
            "total": round(self.total, 2),
        }


def load_bom(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def _install_cost(bom: dict, zones: int) -> float:
    for tier in bom["install_by_zones"]:

        if zones <= tier["max_zones"]:

            return float(tier["cost"])
            
    return float(bom["install_by_zones"][-1]["cost"])


def size_hardware(bom: dict, zones: int, reserve_ml: float, build_storage: bool, has_pump: bool) -> tuple[list[LineItem], float]:
    """Return the itemised hardware list and the total capex for a given system size."""
    items: list[LineItem] = []

    for c in bom["per_zone_kit"]:
        items.append(LineItem(c["item"], c["type"], zones, float(c["unit_cost"])))

    for c in bom["central_kit"]:
        items.append(LineItem(c["item"], c["type"], 1, float(c["unit_cost"])))

    if not has_pump:
        p = bom["optional_pump"]
        items.append(LineItem(p["item"], p["type"], 1, float(p["unit_cost"])))

    items.append(LineItem("Installation and commissioning", "Service", 1, _install_cost(bom, zones)))

    if build_storage:
        items.append(LineItem("Reserve build (lined dam or tank)", "COTS civil", reserve_ml, float(bom["storage_capex_per_ml"])))

    capex = sum(i.total for i in items)
    
    return items, capex


def annual_recurring(bom: dict) -> float:
    return sum(float(c["unit_cost"]) for c in bom["recurring_annual"])
