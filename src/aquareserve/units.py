"""Unit conversions and agronomic constants used across the simulation.

Keeping these in one tested place avoids the classic irrigation-model bug:
mixing depth (mm) with volume (m3) without accounting for area.

Key identity: 1 mm of water depth over 1 hectare = 10 cubic metres.
"""

from __future__ import annotations

# 1 mm over 1 ha == 10 m^3. (1 ha = 10_000 m^2; 1 mm = 0.001 m; 10_000 * 0.001 = 10)
M3_PER_MM_HA: float = 10.0

# 1 megalitre = 1000 m^3
M3_PER_ML: float = 1000.0


def mm_to_m3(depth_mm: float, area_ha: float) -> float:
    """Convert an irrigation/rainfall depth (mm) over an area (ha) to volume (m3)."""
    return depth_mm * area_ha * M3_PER_MM_HA


def m3_to_mm(volume_m3: float, area_ha: float) -> float:
    """Convert a water volume (m3) applied over an area (ha) to an equivalent depth (mm)."""
    if area_ha <= 0:
        raise ValueError("area_ha must be positive")
        
    return volume_m3 / (area_ha * M3_PER_MM_HA)


def ml_to_m3(volume_ml: float) -> float:
    """Convert megalitres to cubic metres."""
    return volume_ml * M3_PER_ML


def m3_to_ml(volume_m3: float) -> float:
    """Convert cubic metres to megalitres."""
    return volume_m3 / M3_PER_ML
