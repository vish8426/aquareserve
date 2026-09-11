"""AquaReserve dashboard backend

A thin read-and-serve API over the precomputed results store.
It never runs the simulation engine: the ``aquareserve`` core precomputes the scenario x controller x reserve-size matrix (``scripts/run_matrix.py``) and this service just queries it and the scenario config, so the deployed dashboard is fast and stateless (precompute and serve).
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
