"""Load and assemble a validated :class:`Scenario` from YAML configuration.

Usage
-----
>>> from aquareserve.config import load_scenario >>> scenario = load_scenario("config/farm.example.yaml") >>> scenario.total_area_ha 24.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import ClimateConfig, CropModel, EconomicsConfig, Farm, Reserve, Scenario

# Default locations relative to a farm config file's directory
DEFAULT_CLIMATE_FILE = "climate.example.yaml"
DEFAULT_CROPS_DIR = "crops"


def _read_yaml(path: Path) -> dict[str, Any]:

    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"expected a mapping at the top of {path}, got {type(data)}")

    return data


def load_crop_models(crops_dir: Path) -> dict[str, CropModel]:

    """Load every ``*.yaml`` crop pack in ``crops_dir`` keyed by crop name."""
    if not crops_dir.is_dir():
        raise FileNotFoundError(f"crops directory not found: {crops_dir}")

    models: dict[str, CropModel] = {}

    for yml in sorted(crops_dir.glob("*.yaml")):
        model = CropModel(**_read_yaml(yml))

        if model.name in models:
            raise ValueError(f"duplicate crop name '{model.name}' in {yml}")

        models[model.name] = model

    if not models:
        raise ValueError(f"no crop model packs (*.yaml) found in {crops_dir}")

    return models


def _resolve_reserve(farm: Farm, base_dir: Path) -> Reserve:
    """Return an inline reserve or load the one referenced by ``reserve_ref``."""
    if farm.reserve is not None:
        return farm.reserve
        
    if farm.reserve_ref is not None:
        return Reserve(**_read_yaml(base_dir / farm.reserve_ref))

    raise ValueError("farm config must provide either 'reserve' or 'reserve_ref'")


def load_scenario(
    farm_path: str | Path,
    climate_path: str | Path | None = None,
    crops_dir: str | Path | None = None,
) -> Scenario:
    """Assemble a fully-validated :class:`Scenario`.

    Parameters
    ----------
    farm_path:
        Path to the farm YAML. Its parent directory is used to resolve the
        climate file, crops directory and any ``reserve_ref``.
    climate_path:
        Override for the climate config (defaults to ``<dir>/climate.example.yaml``).
    crops_dir:
        Override for the crop packs directory (defaults to ``<dir>/crops``).
    """
    farm_path = Path(farm_path)
    base_dir = farm_path.parent

    farm = Farm(**_read_yaml(farm_path))
    farm.reserve = _resolve_reserve(farm, base_dir)

    climate_file = Path(climate_path) if climate_path else base_dir / DEFAULT_CLIMATE_FILE
    climate = ClimateConfig(**_read_yaml(climate_file))

    crops_path = Path(crops_dir) if crops_dir else base_dir / DEFAULT_CROPS_DIR
    crops = load_crop_models(crops_path)

    # Only keep crop packs actually referenced by the farm (keeps Scenario lean, but validation below still guarantees every zone crop is present).
    referenced = {z.crop for z in farm.zones}
    crops = {name: m for name, m in crops.items() if name in referenced} or crops

    return Scenario(farm=farm, crops=crops, climate=climate)


def load_economics(path: str | Path) -> EconomicsConfig:
    """Load the economic assumptions for the cost/ROI model."""
    return EconomicsConfig(**_read_yaml(Path(path)))
