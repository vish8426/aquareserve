import type { EChartsOption } from "echarts";
import { useState } from "react";
import { api, type ConfigureRequest, type ConfigureResult, type Meta, type ZoneProfile } from "../api";
import { money, t0, t1 } from "../format";
import Chart from "./Chart";

// Configurator wizard: a short farm profile - a sized system, an estimated outcome and an indicative quote.
// Calls POST /api/configure, which runs the validated engine, so a result takes a few seconds.
export default function Configurator({ meta }: { meta: Meta }) {

  const cropOptions = Array.from(new Set(meta.zones.map((z) => z.crop)));
  const [zones, setZones] = useState<ZoneProfile[]>(

    meta.zones.map((z) => ({ crop: z.crop, area_ha: z.area_ha, irrigation: z.irrigation_system === "drip" ? "drip" : "broadacre" })),
  );

  const [existingReserve, setExistingReserve] = useState<string>("");
  const [licenceCap, setLicenceCap] = useState<string>("");
  const [hasPump, setHasPump] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConfigureResult | null>(null);
  const [lastReq, setLastReq] = useState<ConfigureRequest | null>(null);

  const setZone = (i: number, patch: Partial<ZoneProfile>) => setZones((zs) => zs.map((z, j) => (j === i ? { ...z, ...patch } : z)));
  const addZone = () => setZones((zs) => [...zs, { crop: cropOptions[0], area_ha: 4, irrigation: "broadacre" }]);
  const removeZone = (i: number) => setZones((zs) => zs.filter((_, j) => j !== i));

  async function submit() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {

      const req: ConfigureRequest = {

        zones: zones.map((z) => ({ crop: z.crop, area_ha: Number(z.area_ha), irrigation: z.irrigation })),
        existing_reserve_ml: existingReserve ? Number(existingReserve) : null,
        licence_cap_ml: licenceCap ? Number(licenceCap) : null,
        has_pump: hasPump,
      };

      setLastReq(req);
      const res = await api.configure(req);
      setResult(res);

    } catch (e: unknown) {

      setError(e instanceof Error ? e.message : String(e));
    } finally {

      setLoading(false);
    }
  }

  return (
    <>
      <div className="panel">
        <div className="titlebar">
          <span>Configure a System</span>
          <span className="sub">Enter a farm, get a sized system and a payback.</span>
        </div>
        <div className="panel-body">
          <div className="well">
            <table style={{ marginBottom: 10 }}>
              <thead>
                <tr>
                  <th>Crop</th>
                  <th>Area (ha)</th>
                  <th>Irrigation</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {zones.map((z, i) => (
                  <tr key={i}>
                    <td>
                      <select value={z.crop} onChange={(e) => setZone(i, { crop: e.target.value })}>
                        {cropOptions.map((c) => (
                          <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input type="number" min={0.5} step={0.5} value={z.area_ha}
                        onChange={(e) => setZone(i, { area_ha: Number(e.target.value) })} style={{ width: 80 }} />
                    </td>
                    <td>
                      <select value={z.irrigation} onChange={(e) => setZone(i, { irrigation: e.target.value })}>
                        <option value="drip">Drip</option>
                        <option value="broadacre">Broadacre</option>
                      </select>
                    </td>
                    <td>
                      {zones.length > 1 && <button onClick={() => removeZone(i)}>Remove</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="controls" style={{ alignItems: "flex-start" }}>
              <button onClick={addZone}>+ Add Zone</button>
              <div className="field">
                <label htmlFor="er">Existing reserve (ML, blank = recommend)</label>
                <input id="er" type="number" min={0} value={existingReserve}
                  onChange={(e) => setExistingReserve(e.target.value)} style={{ width: 90, height: 28 }} />
              </div>
              <div className="field">
                <label htmlFor="lc">Water licence cap (ML, optional)</label>
                <input id="lc" type="number" min={0} value={licenceCap}
                  onChange={(e) => setLicenceCap(e.target.value)} style={{ width: 90, height: 28 }} />
              </div>
              <div className="field">
                <label htmlFor="pump">Existing pump?</label>
                <div style={{ display: "flex", alignItems: "center", height: 28 }}>
                  <input id="pump" type="checkbox" checked={hasPump} onChange={(e) => setHasPump(e.target.checked)} />
                </div>
              </div>
              <button onClick={submit} disabled={loading} style={{ fontWeight: "bold", marginTop: 18 }}>
                {loading ? "Sizing..." : "Size my System"}
              </button>
            </div>
            <p className="muted" style={{ margin: "8px 0 0" }}>
              Supported crops: {cropOptions.join(", ")}.<br />
              Runs the engine, so a result takes a few seconds.<br />
              All figures are indicative for planning.
            </p>
          </div>
        </div>
      </div>

      {error && <div className="panel"><div className="panel-body status error">{error}</div></div>}

      {result && lastReq && <Result result={result} req={lastReq} />}
    </>
  );
}

function Actions({ result, req }: { result: ConfigureResult; req: ConfigureRequest }) {

  const { design, economics: ec } = result;
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [farm, setFarm] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function download() {

    setBusy(true);
    setMsg(null);

    try {

      const blob = await api.proposal(req);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      a.download = "aquareserve-proposal.pdf";
      a.click();

      URL.revokeObjectURL(url);

    } catch (e: unknown) {

      setMsg(e instanceof Error ? e.message : String(e));

    } finally {

      setBusy(false);
    }
  }

  async function save() {

    setMsg(null);
    setSaved(null);

    if (!name || !email) {

      setMsg("Name and email are required to save.");

      return;
    }
    try {

      const r = await api.saveLead({ \
        ...req,
        contact: { name, email, farm: farm || undefined },
        summary: {
          reserve_ml: design.reserve_ml,
          capex_aud: design.capex_aud,
          payback_years: ec.payback_years,
          npv_aud: ec.npv_aud,
          monthly_eaas_aud: ec.monthly_eaas_aud,
        },
      });

      setSaved(r.id);

    } catch (e: unknown) {
      
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="panel">
      <div className="titlebar"><span>Take it further</span></div>
      <div className="panel-body">
        <div className="well" style={{ marginBottom: 12 }}>
          <button onClick={download} disabled={busy} style={{ fontWeight: 600 }}>
            {busy ? "Preparing..." : "Download proposal (PDF)"}
          </button>
          <span className="muted" style={{ marginLeft: 10 }}>A one-page proposal you can save or print.</span>
        </div>
        <div className="well">
          <div className="controls" style={{ alignItems: "flex-end" }}>
            <div className="field">
              <label htmlFor="ln">Your name</label>
              <input id="ln" type="text" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 160 }} />
            </div>
            <div className="field">
              <label htmlFor="le">Email</label>
              <input id="le" type="text" value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: 200 }} />
            </div>
            <div className="field">
              <label htmlFor="lf">Farm (optional)</label>
              <input id="lf" type="text" value={farm} onChange={(e) => setFarm(e.target.value)} style={{ width: 180 }} />
            </div>
            <button onClick={save}>Save this quote</button>
          </div>
          {saved && <p className="muted" style={{ margin: "8px 0 0" }}>Saved. Reference {saved}. We will be in touch.</p>}
          {msg && <p className="error" style={{ margin: "8px 0 0" }}>{msg}</p>}
        </div>
      </div>
    </div>
  );
}

function Result({ result, req }: { result: ConfigureResult; req: ConfigureRequest }) {
  const { design, outcome, economics: ec } = result;
  const cur = ec.currency;
  const pb = ec.payback_range_years;

  const sweep = design.reserve_sweep;
  const sweepOption: EChartsOption | null = sweep
    ? {
        grid: { left: 10, right: 60, top: 36, bottom: 30, containLabel: true },
        title: { text: `NPV by reserve size (${cur})`, textStyle: { fontSize: 13 } },
        tooltip: { trigger: "axis", valueFormatter: (v) => money(v as number, cur) },
        xAxis: { type: "category", data: Object.keys(sweep).map((s) => `${s} ML`), name: "Reserve" },
        yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${Math.round(v / 1000)}k` } },
        
        series: [
          {
            type: "bar",
            data: Object.entries(sweep).map(([ml, v]) => ({
              value: v.npv_aud,
              itemStyle: { color: Number(ml) === design.reserve_ml ? "#1f5136" : "#9aa0a6" },
            })),
            label: { show: true, position: "top", fontSize: 10, formatter: (p) => t0(p.value as number) },
          },
        ],
      }
    : null;

  return (
    <>
      <div className="panel">
        <div className="titlebar">
          <span>Recommended system</span>
          <span className="sub">{design.reserve_basis}</span>
        </div>
        <div className="panel-body">
          <div className="kpis">
            <div className="well kpi">
              <div className="v">{design.reserve_ml} ML</div>
              <div className="l">Reserve ({design.zones} zones)</div>
            </div>
            <div className="well kpi">
              <div className="v">{money(design.capex_aud, cur)}</div>
              <div className="l">System capex</div>
            </div>
            <div className="well kpi">
              <div className="v" style={{ color: "var(--ink-green)" }}>
                {ec.payback_years ? `${t1(ec.payback_years)} yr` : "-"}
              </div>
              <div className="l">Payback{pb ? ` (${t1(pb[0])}-${t1(pb[1])})` : ""}</div>
            </div>
            <div className="well kpi">
              <div className="v">{money(ec.npv_aud, cur)}</div>
              <div className="l">10-yr NPV</div>
            </div>
            <div className="well kpi">
              <div className="v">{money(ec.monthly_eaas_aud, cur)}</div>
              <div className="l">Per month (lease)</div>
            </div>
          </div>
          {result.licence?.capped && (
            <p className="muted" style={{ margin: "10px 0 0" }}>
              <strong style={{ color: "var(--ink-amber)" }}>Held to your water licence.</strong>{" "}
              The reserve is capped at {result.licence.cap_ml} ML. The NPV-optimal size would be{" "}
              {result.licence.uncapped_reserve_ml} ML
              {result.licence.forgone_production_t
                ? `, forgoing about ${t1(result.licence.forgone_production_t)} t of drought-year production`
                : ""}
              ; a larger entitlement would allow more protection.
            </p>
          )}
        </div>
      </div>

      <div className="grid2">
        <div className="panel">
          <div className="titlebar"><span>Estimated outcome (severe drought)</span></div>
          <div className="panel-body">
            <div className="well">
              <table>
                <tbody>
                  <tr><td>Production</td><td>{t1(outcome.production_t)} t</td></tr>
                  <tr className="rainfed"><td>Rainfed (no system)</td><td>{t1(outcome.rainfed_t)} t</td></tr>
                  <tr><td>Yield protected</td><td>+{t0(outcome.yield_protected_pct)}%</td></tr>
                  <tr><td>Water used</td><td>{t1(outcome.water_used_ml)} ML</td></tr>
                  <tr><td>Reserve survival</td><td>{outcome.reserve_survival_days} days</td></tr>
                </tbody>
              </table>
              <div style={{ marginTop: 8 }}>
                {Object.entries(outcome.crops).map(([crop, c]) => (
                  <span key={crop} className={`badge ${c.marketable ? "green" : "red"}`} style={{ marginRight: 6 }}>
                    {crop} {Math.round(c.relative_yield * 100)}% {c.marketable ? "marketable" : "at risk"}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="titlebar"><span>Reserve sizing</span></div>
          <div className="panel-body">
            {sweepOption ? (
              <div className="well"><Chart option={sweepOption} height={260} /></div>
            ) : (
              <div className="well muted">Using the existing reserve; no new build sized.</div>
            )}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="titlebar"><span>Hardware and quote</span></div>
        <div className="panel-body">
          <div className="well" style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr><th>Item</th><th>Type</th><th>Qty</th><th>Unit</th><th>Total</th></tr>
              </thead>
              <tbody>
                {design.hardware.map((h, i) => (
                  <tr key={i}>
                    <td>{h.item}</td>
                    <td>{h.type}</td>
                    <td>{h.qty}</td>
                    <td>{money(h.unit_cost, cur)}</td>
                    <td>{money(h.total, cur)}</td>
                  </tr>
                ))}
                <tr>
                  <td colSpan={4} style={{ textAlign: "right", fontWeight: "bold" }}>Capex</td>
                  <td style={{ fontWeight: "bold" }}>{money(design.capex_aud, cur)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <Actions result={result} req={req} />
    </>
  );
}
