import type { EChartsOption } from "echarts";
import { api } from "../api";
import { CONTROLLER_COLORS, CONTROLLER_SHORT, money, t0, t1 } from "../format";
import { useAsync } from "../hooks";
import Chart from "./Chart";

// Economics tab: capex, expected annual benefit, payback and NPV per controller at the chosen reserve size.
// Expected returns blend the normal and severe seasons by the drought probability - all arithmetic over the precomputed store.
export default function RoiPanel({ reserveMl }: { reserveMl: number }) {
  const { value: roi, error, loading } = useAsync(() => api.roi(reserveMl), [reserveMl]);

  if (loading) return <div className="status">Loading economics...</div>;
  if (error) return <div className="status error">{error}</div>;
  if (!roi) return null;

  const cur = roi.currency;
  const ordered = [...roi.controllers].sort((a, b) => a.npv - b.npv);
  const npvOption: EChartsOption = {
    grid: { left: 10, right: 72, top: 36, bottom: 28, containLabel: true },
    title: { text: `Net present value - ${cur} (${roi.horizon_years}-yr)`, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => money(v as number, cur) },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (v: number) => `${Math.round(v / 1000)}k` },
    },
    yAxis: {
      type: "category",
      data: ordered.map((c) => CONTROLLER_SHORT[c.controller] ?? c.label),
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        type: "bar",
        data: ordered.map((c) => ({
          value: c.npv,
          itemStyle: { color: CONTROLLER_COLORS[c.controller] ?? "#1565c0" },
        })),
        label: { show: true, position: "right", fontSize: 11, formatter: (p) => t0(p.value as number) },
      },
    ],
  };

  return (
    <>
      <div className="panel">
        <div className="titlebar">
          <span>Investment case</span>
          <span className="sub">reserve {roi.reserve_ml} ML</span>
        </div>
        <div className="panel-body">
          <div className="kpis">
            <div className="well kpi">
              <div className="v">{money(roi.capex, cur)}</div>
              <div className="l">System capex</div>
            </div>
            <div className="well kpi">
              <div className="v">{(roi.severe_year_probability * 100).toFixed(0)}%</div>
              <div className="l">Severe-year probability</div>
            </div>
            <div className="well kpi">
              <div className="v">{(roi.discount_rate * 100).toFixed(0)}%</div>
              <div className="l">Discount rate</div>
            </div>
            <div className="well kpi">
              <div className="v">{roi.horizon_years} yr</div>
              <div className="l">Analysis horizon</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="panel">
          <div className="titlebar"><span>NPV by controller</span></div>
          <div className="panel-body">
            <div className="well"><Chart option={npvOption} height={300} /></div>
          </div>
        </div>
        <div className="panel">
          <div className="titlebar"><span>Payback and returns</span></div>
          <div className="panel-body">
            <div className="well" style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Controller</th>
                    <th>Exp. annual benefit</th>
                    <th>Payback (yr)</th>
                    <th>NPV</th>
                  </tr>
                </thead>
                <tbody>
                  {[...roi.controllers]
                    .sort((a, b) => b.npv - a.npv)
                    .map((c) => (
                      <tr key={c.controller}>
                        <td>
                          {c.label}
                          {!c.deployable && <span className="badge amber" style={{ marginLeft: 6 }}>ref</span>}
                        </td>
                        <td>{money(c.expected_annual_benefit, cur)}</td>
                        <td>{c.payback_years === null ? "never" : t1(c.payback_years)}</td>
                        <td>{money(c.npv, cur)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
