"""AquaReserve configurator.

Turns a short farm profile into a sized system, an estimated outcome and an indicative quote with payback, running entirely on the validated simulation core.
This is the bridge from the project toward a sellable product; see docs/CONFIGURATOR_SPEC.md.
"""

from .bom import LineItem, annual_recurring, load_bom, size_hardware
from .core import FarmProfile, ZoneInput, build_scenario, configure

__all__ = [
    "FarmProfile",
    "ZoneInput",
    "configure",
    "build_scenario",
    "load_bom",
    "size_hardware",
    "annual_recurring",
    "LineItem",
]
