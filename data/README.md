# Data/
Climate data for AquaReserve. 

Large or downloaded files under `data/raw/` are git-ignored; only this README and small fixtures are tracked.

## Source
Weather is real daily data from **SILO** (Queensland Government, Long Paddock service), station **76031 Mildura Airport** (-34.24, 142.09, 50 m), in the FAO-56 format which includes FAO-56 Penman-Monteith short-crop ET0. SILO data are licensed CC BY 4.0. 

See https://www.longpaddock.qld.gov.au/silo.

## Current File
`data/raw/silo_mildura.txt` currently covers **2000-01-01 to 2001-04-09** (one full winter cropping season, 2000). 

The loader parses it via `aquareserve.weather.silo`. 

If the file is absent, the loader falls back to deterministic synthetic weather so tests and CI still run offline.

## Getting the Full Record
To extend to the full 2000-2023 (or 1889-present) record:

```bash
python scripts/fetch_silo.py --email you@example.com \
    --station 76031 --start 20000101 --finish 20231231 \
    --out data/raw/silo_mildura.txt
```

Then set `period.end` in `config/climate.example.yaml` to match the new range.


(Alternatively, download via the SILO web form at https://www.longpaddock.qld.gov.au/silo/point-data and choose the "FAO56" format.)

## Calibration Note
Crop reference yields are irrigated potentials; soil water-holding (PAWC) and the sowing-time soil-water deficit are set to Mallee sandy-loam values so that *rainfed* cereal yields land near the real dryland average (~2 t/ha). 

Rigorous multi-year calibration and cross-validation against pyfao56 and AquaCrop-OSPy.
