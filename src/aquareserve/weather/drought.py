"""Drought injection - transform a historical/synthetic record into a scenario.

A :class:`DroughtScenario` scales daily rainfall down (rainfall_multiplier < 1) and optionally scales evaporative demand up (et0_multiplier > 1) to emulate the hotter, drier conditions that accompany drought.
This keeps the temporal structure of the real record while stressing the water balance in a controlled, repeatable way.
"""

from __future__ import annotations

import pandas as pd

from ..config.schema import DroughtScenario
from . import columns as C


def apply_drought(df: pd.DataFrame, scenario: DroughtScenario) -> pd.DataFrame:
    """Return a copy of ``df`` with the scenario's multipliers applied.

    Rainfall is scaled by ``rainfall_multiplier``; ET0 by ``et0_multiplier``.
    The original DataFrame is not modified.
    """
    out = df.copy()
    out[C.RAIN] = out[C.RAIN] * scenario.rainfall_multiplier
    out[C.ET0] = out[C.ET0] * scenario.et0_multiplier
    
    return out


def find_scenario(scenarios: list[DroughtScenario], name: str) -> DroughtScenario:
    """Look up a drought scenario by name or raise a clear error."""
    for s in scenarios:
        if s.name == name:
            return s

    available = ", ".join(s.name for s in scenarios) or "(none)"
    
    raise KeyError(f"drought scenario '{name}' not found; available: {available}")
