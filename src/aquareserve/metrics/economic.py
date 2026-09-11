"""Cost / ROI model.

Turns the agronomic results into money: the capital cost of the AquaReserve system, the annual gross-margin uplift each controller delivers over doing nothing (rainfed) and the resulting payback period and net present value.
Because returns depend on the weather, the expected annual benefit blends a normal and a severe drought year by the configured drought probability.

It also frames the central trade-off: a farmer can protect yield either by building a bigger dam (capital) or by running smarter control software (nearly free).
The `dam_capacity_to_match` helper measures how much extra storage the naive rule would need to match a smart controller, valuing the storage the software displaces.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config.schema import EconomicsConfig, Scenario
from .agronomic import FarmMetrics


@dataclass
class ControllerEconomics:
    controller: str
    capex: float
    annual_benefit_normal: float
    annual_benefit_severe: float
    expected_annual_benefit: float

    # None if the system never pays back
    payback_years: float | None  
    npv: float


def system_capex(scenario: Scenario, econ: EconomicsConfig) -> float:
    """One-off capital cost: storage build + per-zone hardware + gateway + install."""
    storage = scenario.farm.reserve.capacity_m3 * econ.costs.storage_capex_per_m3
    n_zones = len(scenario.farm.zones)
    hardware = n_zones * econ.costs.per_zone_hardware + econ.costs.gateway

    return storage + hardware + econ.costs.install


def production_value(metrics: FarmMetrics, scenario: Scenario) -> float:
    """Gross value of production [currency] at farmgate crop prices."""
    crops = scenario.crops

    return sum(z.production_t * crops[z.crop].price_per_t for z in metrics.zones)


def annual_benefit(controller: FarmMetrics, rainfed: FarmMetrics, scenario: Scenario, econ: EconomicsConfig) -> float:
    """Net annual benefit of running the system vs rainfed: production uplift less ongoing operating and subscription costs.
    """
    uplift = production_value(controller, scenario) - production_value(rainfed, scenario)

    return uplift - econ.costs.annual_opex - econ.costs.subscription_per_year


def npv(capex: float, annual: float, econ: EconomicsConfig) -> float:
    """Net present value over the analysis horizon."""
    r = econ.discount_rate

    return -capex + sum(annual / (1 + r) ** y for y in range(1, econ.horizon_years + 1))


def evaluate(
    controller_normal: FarmMetrics, rainfed_normal: FarmMetrics,
    controller_severe: FarmMetrics, rainfed_severe: FarmMetrics,
    scenario: Scenario, econ: EconomicsConfig,
) -> ControllerEconomics:

    """Full economics for one controller across a normal and a severe year."""
    capex = system_capex(scenario, econ)

    b_norm = annual_benefit(controller_normal, rainfed_normal, scenario, econ)
    b_sev = annual_benefit(controller_severe, rainfed_severe, scenario, econ)
    p = econ.severe_year_probability

    expected = (1 - p) * b_norm + p * b_sev

    payback = capex / expected if expected > 0 else None

    return ControllerEconomics(
        controller=controller_normal.controller,
        capex=capex,
        annual_benefit_normal=b_norm,
        annual_benefit_severe=b_sev,
        expected_annual_benefit=expected,
        payback_years=payback,
        npv=npv(capex, expected, econ),
    )


def dam_capacity_to_match(target_production_t: float, productions_by_capacity: dict[float, float]) -> float | None:
    """Smallest reserve capacity (ML) whose production meets a target, by interpolation.

    ``productions_by_capacity`` maps capacity (ML) -> production (t) for a baseline controller.
    Returns the ML needed to match ``target_production_t`` (linear interpolation between the bracketing sizes) or None if no size reaches it.
    """
    sizes = sorted(productions_by_capacity)
    prev_s = prev_p = None

    for s in sizes:
        p = productions_by_capacity[s]

        if p >= target_production_t:
            if prev_s is None or p == prev_p:
                return s

            frac = (target_production_t - prev_p) / (p - prev_p)

            return prev_s + frac * (s - prev_s)

        prev_s, prev_p = s, p

    return None
