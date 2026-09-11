import type { EChartsOption } from "echarts";
import { api, type Meta } from "../api";
import { CONTROLLER_COLORS, CONTROLLER_SHORT, t0, t1 } from "../format";
import { useAsync } from "../hooks";
import Chart from "./Chart";

// main tab: how every controller protects yield in the chosen season and reserve size, against the rainfed (no-system) baseline.
// this is the core "does the system save crops" evidence, straight from the precomputed store.
export default function ControllerComparison({
  meta,
  year,
  reserveMl,
}: {
  meta: Meta;
  year: string;
  reserveMl: number;
}) {
  const { value: rows, error, loading } = useAsync(
    () => api.comparison(year, reserveMl),
    [year, reserveMl],
  );

  if (loading) return <div className="status">Loading comparison...</div>;
  if (error) return <div className="status error">{error}</div>;
  if (!rows) return null;

  const rainfed = rows.find((r) => r.controller === "rainfed");
  const deployable = rows.filter((r) => meta.controllers.find((c) => c.id === r.controller)?.deployable);
  const best = deployable[0] ?? rows[0];
  const yearLabel = meta.years.find((y) => y.id === year)?.label ?? year;
  const cropCols = meta.zones.map((z) => `${z.crop}_t_ha`);

  // ascending for a bar
  const ordered = [...rows].sort((a, b) => a.production_t - b.production_t); 

  const option: EChartsOption = {
    grid: { left: 10, right: 56, top: 36, bottom: 32, containLabel: true },
    title: {
      text: `Season production (t) - ${yearLabel} at ${reserveMl} ML`,
      textStyle: { fontSize: 13 },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v) => `${t1(v as number)} t`,
    },
    xAxis: { type: "value", name: "Production (t)", nameLocation: "middle", nameGap: 24 },

    yAxis: {
      type: "category",
      data: ordered.map((r) => CONTROLLER_SHORT[r.controller] ?? r.label),
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        type: "bar",
        data: ordered.map((r) => ({
          value: r.production_t,
          itemStyle: { color: CONTROLLER_COLORS[r.controller] ?? "#1565c0" },
        })),
        label: { show: true, position: "right", fontSize: 11, formatter: (p) => `${t0(p.value as number)}` },
        markLine: rainfed
          ? {
              symbol: "none",
              data: [{ xAxis: rainfed.production_t, name: "rainfed" }],
              lineStyle: { color: "#9e9e9e", type: "dashed" },
              label: { formatter: "rainfed", position: "insideEndTop" },
            }
          : undefined,
      },
    ],
  };

  return (
    <>
      <div className="panel">
        <div className="titlebar">
          <span>Yield protection</span>
          <span className="sub">{yearLabel}</span>
        </div>
        <div className="panel-body">
          <div className="kpis">
            <div className="well kpi">
              <div className="v">{t0(best.production_t)} t</div>
              <div className="l">Best deployable ({best.label})</div>
            </div>
            <div className="well kpi">
              <div className="v" style={{ color: "var(--ink-green)" }}>+{t0(best.saved_t)} t</div>
              <div className="l">Saved vs rainfed</div>
            </div>
            <div className="well kpi">
              <div className="v" style={{ color: "var(--ink-green)" }}>+{t0(best.saved_pct)}%</div>
              <div className="l">Yield uplift</div>
            </div>
            <div className="well kpi">
              <div className="v">{rainfed ? t0(rainfed.production_t) : "-"} t</div>
              <div className="l">Rainfed (no system)</div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="titlebar"><span>Controller comparison</span></div>
        <div className="panel-body">
          <div className="well"><Chart option={option} height={300} /></div>
        </div>
      </div>

      <div className="panel">
        <div className="titlebar"><span>Detail</span></div>
        <div className="panel-body">
          <div className="well" style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Controller</th>
                  <th>Production (t)</th>
                  <th>Saved (t)</th>
                  <th>Uplift</th>
                  <th>Irrigation (ML)</th>
                  <th>Reserve survival (days)</th>
                  {cropCols.map((c) => (
                    <th key={c}>{c.replace("_t_ha", "")} (t/ha)</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.controller} className={r.controller === "rainfed" ? "rainfed" : ""}>
                    <td>{r.label}</td>
                    <td>{t1(r.production_t)}</td>
                    <td>{r.controller === "rainfed" ? "-" : `+${t1(r.saved_t)}`}</td>
                    <td>{r.controller === "rainfed" ? "-" : `+${t0(r.saved_pct)}%`}</td>
                    <td>{t1(r.irrigation_ml)}</td>
                    <td>{r.survival_days}</td>
                    {cropCols.map((c) => (
                      <td key={c}>{typeof r[c] === "number" ? t1(r[c] as number) : "-"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
