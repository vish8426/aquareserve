# Farm Digital Twin (2D Top-Down Viewer)

`farm_twin.html` is a self-contained, offline visualisation of the AquaReserve simulation. Open it in any browser - no server needed. It plays back **real engine output** day by day for the mixed Mallee farm (onion drip, wheat, barley) sharing the
finite 20ML reserve:

- each field is coloured by crop health (the FAO-56 stress coefficient Ks) and grows through its stages, with a soil-moisture bar showing root-zone depletion; 
- the reserve tank drains and refills, with irrigation flows drawn from the reserve to each field on the days it waters;
- live readouts show per-field health, growth, relative and projected yield, plus the season's production, farmgate value and reserve survival.

Switch the controller (rainfed through robust MPC and the oracle) and the season (normal vs severe drought) to compare how each strategy spends the shared water.

## Regenerate

```
python scripts/export_twin.py          # rebuild farm_twin.html from the engine
python scripts/export_twin.py --json    # also emit viz/twin_data.json
```

`export_twin.py` runs the engine for every controller across both seasons and injects a compact JSON payload into `_template.html`. Numbers in the viewer match `compute_metrics` exactly (production, irrigation, reserve survival).
