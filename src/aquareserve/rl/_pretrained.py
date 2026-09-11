"""Pretrained RL policy weights.

Weights found by the Cross-Entropy Method (rl.cem) on the real contrasting seasons used by the twin (real 2000 normal and the real 2019 drought), each scenario normalised to its own rainfed->oracle range.
Committed so the RL controller is reproducible in the comparison and demo without re-running training.
Regenerate with ``python scripts/train_rl.py --save``.
"""

# Order matches LinearPolicyController._features (see policy.py).
PRETRAINED_WEIGHTS = [
    -0.612, 0.261, 0.642, -0.19, -0.873, -2.859, -2.243, -0.494, -0.503, 0.562, -1.093,
]
