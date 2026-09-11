"""Irrigation control strategies.

Public API:
    Controller, ZoneControlContext - the strategy interface
    RainfedController, FixedScheduleController, ThresholdController - baselines
    SmartCriticalStageController - rule-based critical-stage deficit
    MPCController - receding-horizon linear MPC over the reserve
    OracleController - MPC with perfect foresight, an upper-bound benchmark
    StochasticMPCController - robust quantile MPC on an ensemble forecast

The RL comparison policy lives in the sibling ``aquareserve.rl`` package.
"""

from .base import Controller, ZoneControlContext
from .baselines import FixedScheduleController, RainfedController, ThresholdController
from .mpc import MPCController
from .oracle import OracleController
from .smart_rule import SmartCriticalStageController
from .stochastic_mpc import StochasticMPCController

__all__ = [
    "Controller",
    "ZoneControlContext",
    "RainfedController",
    "FixedScheduleController",
    "ThresholdController",
    "SmartCriticalStageController",
    "MPCController",
    "OracleController",
    "StochasticMPCController",
]
