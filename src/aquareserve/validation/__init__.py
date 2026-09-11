"""Independent validation of the AquaReserve engine against published models.

Compares our transparent FAO-56/FAO-33 engine against pyfao56 (and AquaCrop-OSPy) on shared scenarios, quantifying agreement.
See scripts/validate_engine.py.
"""

from .compare import AgreementMetrics, agreement, run_aquareserve_season

__all__ = ["run_aquareserve_season", "agreement", "AgreementMetrics"]
