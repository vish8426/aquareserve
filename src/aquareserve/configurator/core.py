"""Configurator core.

Maps a short farm profile to a sized system, an estimated outcome and an indicative quote with payback.
It runs entirely on the validated simulation core: it builds a Scenario from the profile, recommends a reserve size by maximising the farmer's NPV over candidate sizes, runs the engine under a normal and a severe season then prices the result from the hardware BOM plus the economics config.
Every number traces to the engine, the BOM or the economics config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import load_scenario
from ..config.loader import load_economics
from ..controllers import MPCController, RainfedController
from ..experiments import resize_reserve
from ..metrics import compute_metrics, production_value
from ..simulation import SimulationEngine
from ..weather import load_weather
from .bom import annual_recurring, load_bom, size_hardware

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "config"

PLANTING = "2000-05-01"

# relative-yield threshold for a marketable crop
MARKETABLE = 0.70  
SIZING_CANDIDATES_ML = [10, 20, 30, 40]
EAAS_TERM_MONTHS = 60

# indicative lease rate for the equipment-as-a-service monthly figure
EAAS_RATE = 0.10  


@dataclass
class ZoneInput:
    crop: str
    area_ha: float
    irrigation: str | None = None


@dataclass
class FarmProfile:
    zones: list[ZoneInput]
    region: str = "mallee"
    existing_reserve_ml: float | None = None
    has_pump: bool = False
    price_scale: float = 1.0
    discount_rate: float | None = None
    severe_year_probability: float | None = None

    # water-licence / allocation cap on the reserve
    licence_cap_ml: float | None = None  


def _template_scenario():
    return load_scenario(CONFIG / "farm.example.yaml")


def build_scenario(profile: FarmProfile, reserve_ml: float):
    """Construct a Scenario from the profile, reusing per-crop zone templates from the example farm and resizing the reserve.
    Unsupported crops raise (only the modeled crops are covered).
    """
    base = _template_scenario()
    templates = {z.crop: z for z in base.farm.zones}
    unknown = [z.crop for z in profile.zones if z.crop not in templates]

    if unknown:
        raise ValueError(
            f"Unsupported crop(s) for the configurator: {sorted(set(unknown))}. "
            f"Supported: {sorted(templates)}."
        )

    if not profile.zones:
        raise ValueError("At least one crop zone is required.")

    sc = base.model_copy(deep=True)
    zones = []

    for i, z in enumerate(profile.zones, start=1):
        zt = templates[z.crop].model_copy(deep=True)
        zt.id = f"{z.crop}-{i}"
        zt.area_ha = float(z.area_ha)
        zones.append(zt)

    sc.farm.zones = zones

    return resize_reserve(sc, reserve_ml)


def _weather(sc, year: str):
    return load_weather(sc.climate, scenario_name=year, base_dir=str(REPO_ROOT))


def _run(sc, controller, weather):
    engine = SimulationEngine(sc, weather, planting_date=PLANTING)
    return compute_metrics(engine.run(controller), sc)


def _is_hort(sc, zone_id: str) -> bool:
    z = next((z for z in sc.farm.zones if z.id == zone_id), None)
    return bool(z and z.irrigation_system == "drip")


def _economics(capex, uplift_n, uplift_s, fixed, p, r, horizon, scale):
    def expected(sf):
        return (1 - p) * (sf * uplift_n - fixed) + p * (sf * uplift_s - fixed)

    exp = expected(scale)
    payback = capex / exp if exp > 0 else None
    npv = -capex + sum(exp / (1 + r) ** y for y in range(1, horizon + 1))

    # low price -> longer
    pb_hi = capex / expected(scale * 0.8) if expected(scale * 0.8) > 0 else None

    # high price -> shorter
    pb_lo = capex / expected(scale * 1.2) if expected(scale * 1.2) > 0 else None 

    return exp, payback, npv, pb_lo, pb_hi


def _eaas_monthly(capex: float, annual_opex: float) -> float:
    rm = EAAS_RATE / 12.0
    n = EAAS_TERM_MONTHS
    cap_monthly = capex * rm / (1 - (1 + rm) ** -n)

    return round(cap_monthly + annual_opex / 12.0, 0)


@dataclass
class _Cache:
    weather: dict = field(default_factory=dict)

    # year -> (production_t, production_value) reserve-independent
    rainfed: dict = field(default_factory=dict)  


def _evaluate(profile, reserve_ml, build_storage, bom, econ, cache: _Cache) -> dict:
    sc = build_scenario(profile, reserve_ml)
    zones = len(profile.zones)

    if not cache.weather:
        cache.weather = {"normal": _weather(sc, "normal"), "severe": _weather(sc, "severe")}

    wx_n, wx_s = cache.weather["normal"], cache.weather["severe"]

    mpc_n = _run(sc, MPCController(sc), wx_n)
    mpc_s = _run(sc, MPCController(sc), wx_s)

    if "normal" not in cache.rainfed:
        rf_n = _run(sc, RainfedController(), wx_n)
        rf_s = _run(sc, RainfedController(), wx_s)

        cache.rainfed["normal"] = (rf_n.total_production_t, production_value(rf_n, sc), rf_n)
        cache.rainfed["severe"] = (rf_s.total_production_t, production_value(rf_s, sc), rf_s)

    rf_s_prod, rf_s_val, _ = cache.rainfed["severe"]
    rf_n_prod, rf_n_val, _ = cache.rainfed["normal"]

    # economics
    p = econ.severe_year_probability if profile.severe_year_probability is None else profile.severe_year_probability
    r = econ.discount_rate if profile.discount_rate is None else profile.discount_rate

    fixed = econ.costs.annual_opex + econ.costs.subscription_per_year

    uplift_n = production_value(mpc_n, sc) - rf_n_val
    uplift_s = production_value(mpc_s, sc) - rf_s_val
    
    items, capex = size_hardware(bom, zones, reserve_ml, build_storage, profile.has_pump)
    exp, payback, npv, pb_lo, pb_hi = _economics(capex, uplift_n, uplift_s, fixed, p, r, econ.horizon_years, profile.price_scale)

    # outcome (severe season)
    saved = mpc_s.total_production_t - rf_s_prod
    yprot = 100.0 * saved / rf_s_prod if rf_s_prod > 0 else 0.0
    crops = {}

    for zm in mpc_s.zones:
        crops[zm.crop] = {
            "relative_yield": round(zm.relative_yield, 3),
            "yield_t_ha": round(zm.yield_t_ha, 2),
            "marketable": bool(zm.relative_yield >= MARKETABLE),
            "horticulture": _is_hort(sc, zm.zone_id),
        }

    pb_range = [x for x in (pb_lo, pb_hi) if x is not None]

    return {
        "design": {
            "reserve_ml": reserve_ml,
            "zones": zones,
            "build_storage": build_storage,
            "controller": "mpc",
            "hardware": [i.as_dict() for i in items],
            "capex_aud": round(capex, 0),
        },
        "outcome": {
            "production_t": round(mpc_s.total_production_t, 1),
            "rainfed_t": round(rf_s_prod, 1),
            "yield_protected_pct": round(yprot, 0),
            "water_used_ml": round(mpc_s.total_irrigation_m3 / 1000.0, 2),
            "reserve_survival_days": int(mpc_s.reserve_survival_days),
            "crops": crops,
        },
        "economics": {
            "currency": econ.currency,
            "capex_aud": round(capex, 0),
            "expected_annual_benefit_aud": round(exp, 0),
            "payback_years": round(payback, 2) if payback is not None else None,
            "payback_range_years": [round(min(pb_range), 2), round(max(pb_range), 2)] if pb_range else None,
            "npv_aud": round(npv, 0),
            "monthly_eaas_aud": _eaas_monthly(capex, annual_recurring(bom)),
            "discount_rate": r,
            "severe_year_probability": p,
            "horizon_years": econ.horizon_years,
        },
    }


def _licence_ml(profile: FarmProfile) -> float | None:
    cap = profile.licence_cap_ml
    return float(cap) if cap is not None and cap > 0 else None


def configure(profile: FarmProfile) -> dict:
    """Size, estimate and price a system for the given farm profile.

    If a water-licence / allocation cap is given, the recommended reserve is hard-capped at the licence: the system never recommends drawing more water than the farm is legally entitled to.
    The forgone yield versus the unconstrained NPV-optimal size is reported.
    """
    bom = load_bom(CONFIG / "bom.yaml")
    econ = load_economics(CONFIG / "economics.example.yaml")
    cache = _Cache()
    licence = _licence_ml(profile)

    existing = profile.existing_reserve_ml

    if existing and existing > 0:
        result = _evaluate(profile, float(existing), build_storage=False, bom=bom, econ=econ, cache=cache)
        result["design"]["reserve_basis"] = "existing reserve (no new build)"
        result["design"]["reserve_sweep"] = None
        result["design"]["licence_cap_ml"] = licence
        result["design"]["licence_capped"] = False
        note = None

        if licence is not None and existing > licence:
            note = (f"The existing reserve of {existing:g} ML exceeds the stated water licence of "
                    f"{licence:g} ML; check the allocation before drawing the full reserve.")

        result["licence"] = {"cap_ml": licence, "capped": False, "note": note}

        return result

    # recommend the reserve size that maximises NPV over the candidate sizes
    evals = {cap: _evaluate(profile, cap, build_storage=True, bom=bom, econ=econ, cache=cache) for cap in SIZING_CANDIDATES_ML}
    best_cap = max(evals, key=lambda c: evals[c]["economics"]["npv_aud"])

    def _sweep() -> dict:
        return {
            int(cap): {
                "production_t": evals[cap]["outcome"]["production_t"],
                "capex_aud": evals[cap]["design"]["capex_aud"],
                "npv_aud": evals[cap]["economics"]["npv_aud"],
                "over_licence": bool(licence is not None and cap > licence),
            }

            for cap in SIZING_CANDIDATES_ML
        }

    # licence cap binds only when the NPV-optimal size exceeds the entitlement
    if licence is not None and best_cap > licence:
        capped = evals.get(licence) or _evaluate(
            profile, licence, build_storage=True, bom=bom, econ=econ, cache=cache
        )

        uncapped = evals[best_cap]

        capped["design"]["reserve_basis"] = (f"capped at water licence ({licence:g} ML); NPV-optimal was {best_cap} ML")
        capped["design"]["licence_cap_ml"] = licence
        capped["design"]["licence_capped"] = True
        capped["design"]["reserve_sweep"] = _sweep()

        capped["licence"] = {
            "cap_ml": licence,
            "capped": True,
            "uncapped_reserve_ml": best_cap,
            "forgone_production_t": round(
                uncapped["outcome"]["production_t"] - capped["outcome"]["production_t"], 1
            ),
            "forgone_npv_aud": round(uncapped["economics"]["npv_aud"] - capped["economics"]["npv_aud"], 0),
            "note": (f"Reserve held to the {licence:g} ML water licence; a larger entitlement would "
                     f"allow up to {best_cap} ML for more drought protection."),
        }

        return capped

    result = evals[best_cap]
    result["design"]["reserve_basis"] = "recommended (max NPV over candidate sizes)"
    result["design"]["licence_cap_ml"] = licence
    result["design"]["licence_capped"] = False
    result["design"]["reserve_sweep"] = _sweep()
    result["licence"] = {"cap_ml": licence, "capped": False, "note": None}
    
    return result
