"""Weather/climate ingestion, ET0 and drought injection.

Public API:
    load_weather(climate, scenario_name=None, ...) -> tidy daily DataFrame
    read_silo_fao56(path)                          -> parse a real SILO fao56 file
    generate_weather(...)                          -> deterministic synthetic series
    et0_penman_monteith(DailyWeather)              -> FAO-56 reference ET0 [mm/day]
    apply_drought(df, scenario)                    -> scenario-perturbed record
"""

from . import columns
from .drought import apply_drought, find_scenario
from .et0 import DailyWeather, et0_penman_monteith
from .loader import load_weather
from .silo import read_silo_fao56
from .synthetic import generate_weather

__all__ = [
    "columns",
    "load_weather",
    "read_silo_fao56",
    "generate_weather",
    "et0_penman_monteith",
    "DailyWeather",
    "apply_drought",
    "find_scenario",
]
