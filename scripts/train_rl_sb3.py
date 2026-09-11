"""Optional deep-RL path: train PPO over the Gymnasium env with Stable-Baselines3.

This is the SOTA deep-RL comparison.
It is intentionally *not* part of CI or the default demo because Stable-Baselines3 pulls in PyTorch (a large dependency) and training is slow; the in-repo, CI-safe RL policy is the CEM one in scripts/train_rl.py.
Install with ``pip install stable-baselines3`` then run this to train and score a PPO agent.

Usage:
    python scripts/train_rl_sb3.py [--timesteps 200000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=200_000)

    args = ap.parse_args()

    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_util import make_vec_env

    except ImportError:
        print("stable-baselines3 not installed. Run: pip install stable-baselines3")

        return 1

    from aquareserve.config import load_scenario
    from aquareserve.rl.env import ReserveIrrigationEnv
    from aquareserve.weather import load_weather

    sc = load_scenario(REPO_ROOT / "config" / "farm.example.yaml")
    wx = load_weather(sc.climate, scenario_name="severe", base_dir=str(REPO_ROOT))

    def make_env():
        return ReserveIrrigationEnv(sc, wx)

    env = make_vec_env(make_env, n_envs=4)
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=args.timesteps)

    eval_env = make_env()
    obs, _ = eval_env.reset(seed=0)
    total, done = 0.0, False

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, r, done, trunc, _ = eval_env.step(action)
        total += r

    print(f"PPO episode return (severe year): {total:.1f}")

    model.save(str(REPO_ROOT / "outputs" / "ppo_reserve"))

    print("model saved -> outputs/ppo_reserve.zip")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
