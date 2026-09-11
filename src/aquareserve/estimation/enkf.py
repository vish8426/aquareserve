"""Ensemble Kalman Filter for root-zone soil-water state estimation.

The EnKF is primed for assimilating soil-moisture observations into crop/soil models.
Instead of tracking a mean and variance analytically (as the EKF does), it represents the state distribution with an ensemble of member states, pushes each through the *nonlinear* soil-water balance and corrects them with the measurement.
This avoids computing a Jacobian and represents non-Gaussian, nonlinear behaviour by sampling - at the cost of running N model copies per step.

For AquaReserve's mildly-nonlinear 1-D depletion state the EnKF is expected to match the EKF closely; providing both turns the estimator choice into a measured comparison rather than an assertion.

State (scalar): root-zone depletion Dr [mm], represented by an ensemble.
"""

from __future__ import annotations

import numpy as np

from ._process import soil_water_step


class RootZoneEnKF:
    """Ensemble Kalman Filter over root-zone depletion.

    Parameters mirror :class:`RootZoneEKF`, plus ``ensemble_size`` and ``seed``.
    """

    def __init__(
        self,
        taw_mm: float,
        depletion_fraction_p: float,
        initial_depletion_mm: float = 0.0,
        initial_variance: float = 100.0,
        process_variance: float = 4.0,
        measurement_variance: float = 100.0,
        ensemble_size: int = 50,
        seed: int = 0,
    ):
        if taw_mm <= 0:
            raise ValueError("taw_mm must be positive")

        if not 0 < depletion_fraction_p < 1:
            raise ValueError("depletion_fraction_p must be in (0, 1)")

        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >= 2")

        self.taw = taw_mm
        self.raw = depletion_fraction_p * taw_mm
        self.Q = float(process_variance)
        self.R = float(measurement_variance)
        self.n = int(ensemble_size)
        self._rng = np.random.default_rng(seed)

        x0 = min(max(0.0, initial_depletion_mm), taw_mm)

        self.members = np.clip(self._rng.normal(x0, np.sqrt(initial_variance), self.n), 0.0, taw_mm)

    def predict(self, rain_mm: float, crop_et_mm: float, irrigation_mm: float = 0.0) -> None:
        """Advance every member through the balance model and add process noise."""
        noise = self._rng.normal(0.0, np.sqrt(self.Q), self.n)

        self.members = np.array(
            [
                soil_water_step(float(x), self.taw, self.raw, rain_mm, crop_et_mm, irrigation_mm)
                for x in self.members
            ]
        )

        self.members = np.clip(self.members + noise, 0.0, self.taw)

    def update(self, measurement_mm: float) -> None:
        """Assimilate a (noisy) depletion measurement with perturbed observations."""
        # ensemble variance (H = 1)
        var = float(np.var(self.members, ddof=1))  
        gain = var / (var + self.R) if (var + self.R) > 0 else 0.0
        perturbed_obs = measurement_mm + self._rng.normal(0.0, np.sqrt(self.R), self.n)

        self.members = np.clip(self.members + gain * (perturbed_obs - self.members), 0.0, self.taw)

    @property
    def depletion_mm(self) -> float:
        return float(np.mean(self.members))

    @property
    def variance(self) -> float:
        return float(np.var(self.members, ddof=1))
