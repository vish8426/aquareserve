import type { EChartsOption } from "echarts";
import { api, type Meta } from "../api";
import { CONTROLLER_COLORS, CONTROLLER_SHORT, t0, t1 } from "../format";
import { useAsync } from "../hooks";
import Chart from "./Chart";

// Reserve-size sensitivity: production as the reserve grows, for the chosen season.
// Shows the diminishing return past the design size (the "software vs a bigger dam" argument).
export default function ReserveSweep({ meta, year }: { meta: Meta; year: string }) {
  const controllers = meta.controllers.filter((c) => c.id !== "rainfed").map((c) => c.id);
  const { value, error, loading } = useAsync(
    () => Promise.all(controllers.map((c) => api.reserveSweep(c, year).then((rows) => ({ c, rows })))),
    [year],
  );

  if (loading) return <div className="status">Loading reserve sweep...</div>;
  if (error) return <div className="status error">{error}</div>;
  if (!value) return null;

  const yearLabel = meta.years.find((y) => y.id === year)?.label ?? year;
  const sizes = meta.reserve_sizes_ml;
  const label = (id: string) => CONTROLLER_SHORT[id] ?? meta.controllers.find((c) => c.id === id)?.label ?? id;

  const option: EChartsOption = {
    grid: { left: 12, right: 24, top: 66, bottom: 46, containLabel: true },
    title: { text: `Production (t) vs reserve size - ${yearLabel}`, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis", valueFormatter: (v) => `${t1(v as number)} t` },
    legend: { top: 26, type: "scroll", left: "center" },
    xAxis: {
      type: "category",
      data: sizes.map((s) => `${s}`),
      name: "Reserve (ML)",
      nameLocation: "middle",
      nameGap: 26,
    },
    yAxis: { type: "value" },
    series: value.map(({ c, rows }) => ({
      name: label(c),
      type: "line",
      smooth: true,
      symbolSize: 6,
      lineStyle: { width: c === "mpc" ? 3 : 1.5 },
      itemStyle: { color: CONTROLLER_COLORS[c] ?? "#1565c0" },
      data: sizes.map((s) => rows.find((r) => r.reserve_ml === s)?.production_t ?? null),
      markLine:
        c === "mpc"
          ? {
              symbol: "none",
              silent: true,
              data: [{ xAxis: `${meta.design_reserve_ml}`, name: "design" }],
              lineStyle: { color: "#b22222", type: "dashed" },
              label: { formatter: "design 20 ML", color: "#b22222" },
            }
          : undefined,
    })),
  };

  // headline: MPC gain from smallest to design size then design to largest (diminishing return)
  const mpc = value.find((v) => v.c === "mpc")?.rows ?? [];
  const at = (s: number) => mpc.find((r) => r.reserve_ml === s)?.production_t ?? 0;
  const first = sizes[0];
  const last = sizes[sizes.length - 1];
  const design = meta.design_reserve_ml;

  return (
    <div className="panel">
      <div className="titlebar">
        <span>Reserve sizing sensitivity</span>
        <span className="sub">{yearLabel}</span>
      </div>
      <div className="panel-body">
        <div className="well"><Chart option={option} height={360} /></div>
        <p className="muted" style={{ marginBottom: 0 }}>
          MPC production rises from {t0(at(first))} t at {first} ML to {t0(at(design))} t at the{" "} {design} ML design reserve, then only to {t0(at(last))} t at {last} ML - a diminishing return that motivates smarter control over simply building a bigger dam.
        </p>
      </div>
    </div>
  );
}
