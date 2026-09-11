# Crop Parameter Packs

Each `*.yaml` here is a **crop-agnostic FAO parameter pack**. 

The engine models any crop from one of these, so adding a crop is a data , not a code change. 

A pack carries the FAO-56 crop coefficients (`kc`), the growth `stage_days`, `root_depth`, the FAO-33 `yield_response` (seasonal Ky plus per-stage sensitivity), the depletion fraction `p`, a seasonal water need, a reference yield and a farmgate price. 

Sources: FAO Irrigation and Drainage Papers 56 (Kc) and 33 (Ky).

## Calibrated Today

- `onion.yaml` - shallow-rooted horticulture, drip, high value, stress-intolerant.
- `wheat.yaml` - broadacre cereal, critical-stage deficit (anthesis and grain fill).
- `barley.yaml` - broadacre cereal, critical-stage deficit.

## Other Commonly Farmed Crops this System can Support/Manage

AquaReserve manages a **Finite Reserve as Supplementary Irrigation**: a little water delivered at the right growth stage to protect yield during drought. 

It suits crops that are high value or have a drought-sensitive critical stage (high Ky), where a small, well-timed volume saves a disproportionate amount of yield. 

Any crop below can be added by writing a pack; the ones marked "calibrated" already ship.

| Crop | Category | Typical irrigation | Fit | Why |
|---|---|---|---|---|
| Onion | Horticulture | Drip | Calibrated | High value, shallow roots, stress-intolerant |
| Wheat | Cereal (Broadacre) | Sprinkler | Calibrated | Sensitive at anthesis and grain fill |
| Barley | Cereal (Broadacre) | Sprinkler | Calibrated | Sensitive at anthesis and grain fill |
| Canola | Oilseed (Broadacre) | Sprinkler | Strong | High Ky at flowering and pod fill; high value |
| Chickpea, Lentil, Field Pea, Faba Bean | Pulse (Broadacre) | Sprinkler | Strong | Flowering and pod fill are water-critical |
| Oats, Triticale | Cereal (Broadacre) | Sprinkler | Strong | Behave like wheat and barley |
| Maize (Corn) | Grain (Summer) | Drip or Pivot | Strong | Very sensitive at silking and tasselling |
| Sorghum, Sunflower | Grain and Oilseed (Summer) | Pivot | Good | Moderate stress response, broad acreage |
| Cotton | Fibre | Drip | Strong | High value, deficit irrigation well established |
| Potato | Horticulture | Drip or spray | Strong | High value, sensitive at tuber initiation and bulking |
| Tomato, Capsicum, Carrot, Lettuce, Brassicas, Garlic, Sweet Corn, Melon, Pumpkin | Horticulture | Drip | Strong | High value per hectare, respond strongly to timely water |
| Lucerne (Alfalfa) | Fodder | Pivot or Flood | Good | Responsive, multi-cut; a perennial pack |
| Winegrapes, Table Grapes, Almonds, Citrus, Olives, Stone Fruit | Perennial Vine and Tree | Drip | Suitable with a Perennial Extension | High value and deficit irrigation is standard, but they need the engine's season loop extended to a multi-year perennial cycle |
| Rice (Paddy) | Cereal (Flooded) | Flood or Ponded | Poor Fit | Flooded culture, not a finite-supplementary paradigm |
| Sugarcane | Grass (Fibre) | Furrow or Pivot | Poor Fit | Very high seasonal water demand, high-rainfall regions |

Practical Notes:

- Best commercial targets are the high-value horticulture and oilseed and pulse crops, where a reserve that survives a few critical weeks turns an unmarketable crop into a marketable one, the same effect the study shows for onion.
- Perennial vines and trees (winegrapes, almonds) are a large, high-value market and deficit irrigation is standard practice there, so they are a strong future target once the engine models a perennial cycle rather than a single annual season.
- Rice and sugarcane are outside the paradigm and are not targeted.

## Adding a Pack

Copy an existing file, fill in the FAO-56 Kc and stage days, the FAO-33 Ky (seasonal and by stage), root depth, `p`, the seasonal water need, a reference yield and a price, then reference the crop from a zone in a farm scenario. 

The configurator and the engine pick it up with no code change.
