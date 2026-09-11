"""Extended Kalman Filter for root-zone soil-water state estimation.

Field soil moisture sensors are noisy and read only occasionally, and a single probe does not see the whole root zone.
The EKF fuses those sparse, noisy readings with the FAO-56 soil water balance *process model* to estimate the true root-zone depletion Dr more accurately than either the raw sensor or the open-loop model alone.
Better state estimates mean the controllers (rule-based, MPC, RL) act on reality, not noise, which is the project's "control under uncertainty" contribution.

State (scalar): root-zone depletion Dr [mm].
Process: Dr_{k+1} = f(Dr_k, rain, ET_c, irrigation) (the soil-water balance step) Measure: z_k = Dr_k + noise (a depletion reading)

The process is nonlinear because the stress coefficient Ks, and hence actual ET, depend on Dr. The EKF linearises f about the current estimate each step (Jacobian F).
"""

from __future__ import annotations

from dataclasses import dataclass

from ._process import soil_water_step, stress_coefficient


@dataclass
class EKFState:
    depletion_mm: float
    variance: float


class RootZoneEKF:
    """1-D Extended Kalman Filter over root-zone depletion.

    Parameters
    ----------
    taw_mm, depletion_fraction_p : soil water-holding + FAO-56 p (define RAW/TAW).
    initial_depletion_mm : starting estimate of Dr. initial_variance : starting estimate uncertainty [mm^2].
    process_variance : Q, model/forcing error added each predict [mm^2].
    measurement_variance : R, sensor noise variance [mm^2].
    """

    def __init__(
        self,
        taw_mm: float,
        depletion_fraction_p: float,
        initial_depletion_mm: float = 0.0,
        initial_variance: float = 100.0,
        process_variance: float = 4.0,
        measurement_variance: float = 100.0,
    ):
        if taw_mm <= 0:
            raise ValueError("taw_mm must be positive")

        if not 0 < depletion_fraction_p < 1:
            raise ValueError("depletion_fraction_p must be in (0, 1)")

        self.taw = taw_mm
        self.raw = depletion_fraction_p * taw_mm
        self.x = min(max(0.0, initial_depletion_mm), taw_mm)
        self.P = float(initial_variance)
        self.Q = float(process_variance)
        self.R = float(measurement_variance)

    # -- helpers ---------------------------------------------------------------
    def _ks(self, dr: float) -> float:
        return stress_coefficient(dr, self.taw, self.raw)

    # -- filter steps ----------------------------------------------------------
    def predict(self, rain_mm: float, crop_et_mm: float, irrigation_mm: float = 0.0) -> None:
        """Advance the estimate one day through the soil-water-balance model."""
        etc = max(0.0, crop_et_mm)
        x_new = soil_water_step(self.x, self.taw, self.raw, rain_mm, crop_et_mm, irrigation_mm)

        # Jacobian dDr_new/dDr: 1 + d(ETa)/dDr, where dKs/dDr = -1/(TAW-RAW) when stressed.
        dks = 0.0 if self.x <= self.raw else -1.0 / (self.taw - self.raw)
        f_jac = 1.0 + etc * dks

        self.x = x_new
        self.P = f_jac * self.P * f_jac + self.Q

    def update(self, measurement_mm: float) -> None:
        """Fuse a (noisy) depletion measurement. Measurement model is identity (H=1)."""
        innovation = measurement_mm - self.x

        # innovation variance
        s = self.P + self.R  

        # Kalman gain
        k = self.P / s  

        self.x = min(max(0.0, self.x + k * innovation), self.taw)
        self.P = (1.0 - k) * self.P

    @property
    def state(self) -> EKFState:
        return EKFState(depletion_mm=self.x, variance=self.P)

    @property
    def depletion_mm(self) -> float:
        return self.x
