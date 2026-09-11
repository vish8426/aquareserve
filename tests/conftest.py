"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture
def config_dir() -> Path:
    """Path to the repository's example config directory."""
    return CONFIG_DIR


@pytest.fixture
def example_farm_path(config_dir: Path) -> Path:
    return config_dir / "farm.example.yaml"
