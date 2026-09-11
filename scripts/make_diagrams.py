"""Generate the documentation diagrams as PNG images from Graphviz sources.

Reproducible: run `python scripts/make_diagrams.py` (requires the Graphviz `dot` binary, e.g. `apt install graphviz` or `brew install graphviz`).
The .dot sources are written to docs/diagrams/src/ and rendered to docs/diagrams/*.png, which are committed and embedded in the Markdown docs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "diagrams"
SRC = OUT / "src"

FONT = "Helvetica"

CONTEXT = f'''
digraph context {{
  rankdir=LR; bgcolor="white"; pad=0.3; nodesep=0.5; ranksep=0.7;
  node [fontname="{FONT}", fontsize=11];
  edge [fontname="{FONT}", fontsize=9, color="#5f6b7a"];

  farmer     [label="Farmer", shape=oval, style=filled, fillcolor="#e8f0fe"];
  agronomist [label="Agronomist", shape=oval, style=filled, fillcolor="#e8f0fe"];
  dash [label="React + TypeScript\\nDashboard (ECharts)", shape=box, style="rounded,filled", fillcolor="#cfe0ff"];
  api  [label="FastAPI service\\n(run control / results)", shape=box, style="rounded,filled", fillcolor="#c9e8d5"];
  core [label="Simulation core (Python)\\nmodels / controllers /\\nestimation / metrics", shape=box, style="rounded,filled", fillcolor="#ffe6c2"];
  data [label="Config (YAML) +\\nclimate data (SILO/BoM) +\\nresults (Parquet/DuckDB)", shape=cylinder, style=filled, fillcolor="#ececec"];

  farmer -> dash;
  agronomist -> dash;
  dash -> api [label="HTTP", dir=both];
  api -> core [label="calls"];
  core -> data [label="reads / writes"];
}}
'''

LOOP = f'''
digraph loop {{
  rankdir=LR; bgcolor="white"; pad=0.3; nodesep=0.45; ranksep=0.75;
  node [fontname="{FONT}", fontsize=11, shape=box, style="rounded,filled"];
  edge [fontname="{FONT}", fontsize=9, color="#5f6b7a"];

  weather [label="Weather\\n(SILO ET0, rain)", fillcolor="#cfe0ff"];
  soil    [label="Soil-water\\nbalance", fillcolor="#c9e8d5"];
  crop    [label="Crop response\\n(ET_c, Ks, yield)", fillcolor="#c9e8d5"];
  ctrl    [label="Controller\\n(rule / MPC / RL)", fillcolor="#ffd9b3"];
  reserve [label="Finite reserve\\n(dam / rain / bore)", fillcolor="#bfe3ef"];
  hardware[label="Modeled hardware\\n(valves / pump)", fillcolor="#e6e6e6"];
  metrics [label="Metrics + cost/ROI", shape=note, fillcolor="#fff3cf"];

  weather -> soil;
  soil -> crop [label="stress state"];
  crop -> ctrl [label="stage / deficit"];
  ctrl -> reserve [label="withdrawal request"];
  reserve -> hardware [label="water"];
  hardware -> soil [label="irrigation", color="#2a7de1", fontcolor="#2a7de1"];
  crop -> metrics [label="yield", style=dashed];
  reserve -> metrics [label="water use", style=dashed];
}}
'''

CONTAINER = f'''
digraph container {{
  rankdir=TB; bgcolor="white"; pad=0.3; nodesep=0.5; ranksep=0.7;
  node [fontname="{FONT}", fontsize=11, shape=box, style="rounded,filled"];
  edge [fontname="{FONT}", fontsize=9, color="#5f6b7a"];

  dash    [label="Dashboard\\nVite + React + TS + ECharts", fillcolor="#cfe0ff"];
  api     [label="API service\\nFastAPI + Uvicorn + DuckDB", fillcolor="#c9e8d5"];
  core    [label="Simulation core\\naquareserve (Python)", fillcolor="#ffe6c2"];
  runner  [label="Experiment runner\\n(scenario x controller matrix)", fillcolor="#ffe6c2"];
  store   [label="Results store\\nParquet + DuckDB", shape=cylinder, fillcolor="#ececec"];
  config  [label="Config (YAML)\\nfarm / crops / climate / reserve", shape=note, fillcolor="#fff3cf"];

  dash -> api [label="HTTP", dir=both];
  api -> store [label="query"];
  runner -> core [label="drives"];
  runner -> store [label="writes results"];
  core -> config [label="reads", dir=back];
}}
'''

DIAGRAMS = {"architecture_context": CONTEXT, "simulation_loop": LOOP, "container_view": CONTAINER}


def main() -> int:
    if shutil.which("dot") is None:
        print("Graphviz 'dot' not found. Install graphviz to regenerate diagrams.", file=sys.stderr)
        
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)

    for name, dot in DIAGRAMS.items():
        dot_path = SRC / f"{name}.dot"
        png_path = OUT / f"{name}.png"
        dot_path.write_text(dot.strip() + "\n", encoding="utf-8")
        subprocess.run(["dot", "-Tpng", "-Gdpi=150", str(dot_path), "-o", str(png_path)], check=True)
        print(f"rendered {png_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
