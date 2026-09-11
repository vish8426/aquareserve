"""Reinforcement-learning comparison policy.

Public API:
    LinearPolicyController - linear irrigation policy, a standard controller
    cem_train, CEMResult   - Cross-Entropy Method policy search on the real engine
    production_value       - farmgate value return signal
"""

from .cem import CEMResult, cem_train, evaluate_weights, production_value
from .policy import N_FEATURES, LinearPolicyController

__all__ = [
    "LinearPolicyController",
    "N_FEATURES",
    "cem_train",
    "CEMResult",
    "evaluate_weights",
    "production_value",
]
