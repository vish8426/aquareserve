import type { EChartsOption } from "echarts";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import Chart from "./Chart";

// Live Monitoring demo.
// No hardware needed: a small soil emulator runs in the browser, drying over time and posting each reading to /api/demo/decide.
// The backend runs the same threshold + critical-stage + finite-reserve logic family as the deployable controllers and returns a pump command, so the tray, the reserve and the decisions on screen tell the same finite-reserve story as the study - and the same loop a real ESP32 node would drive once live telemetry is built.

// the finite "reserve", in miniature
// - soil moisture at sowing
// - % soil moisture lost each step
// - % moisture gained per ml delivered
// - rolling window on the chart
const INITIAL_RESERVE_ML = 400;
const START_MOISTURE = 62; 
const DRY_PER_STEP = 4; 
const ABSORB_PER_ML = 1.2; 
const MAX_POINTS = 80; 

const SPEEDS: Record<string, number> = { Slow: 1100, Normal: 650, Fast: 260 };

interface Point {
  step: number;
  moisture: number;
  reserve: number;
  watered: boolean;
}

function level(pct: number): "green" | "amber" | "red" {

  if (pct >= 50) return "green";
  if (pct >= 20) return "amber";

  return "red";
}

export default function Monitor() {
  const [running, setRunning] = useState(false);
  const [critical, setCritical] = useState(false);
  const [speed, setSpeed] = useState<keyof typeof SPEEDS>("Normal");
  const [moisture, setMoisture] = useState(START_MOISTURE);
  const [reserve, setReserve] = useState(INITIAL_RESERVE_ML);
  const [step, setStep] = useState(0);
  const [waterings, setWaterings] = useState(0);
  const [pumpOn, setPumpOn] = useState(false);
  const [reason, setReason] = useState("Idle - press Start to run the demo.");
  const [history, setHistory] = useState<Point[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Mutable snapshot the loop reads/writes without waiting for React state.
  const s = useRef({ moisture: START_MOISTURE, reserve: INITIAL_RESERVE_ML, step: 0, waterings: 0 });
  const runningRef = useRef(false);
  const criticalRef = useRef(false);
  const speedRef = useRef(SPEEDS.Normal);
  const timer = useRef<number | null>(null);
  const alive = useRef(true);

  useEffect(() => {

    alive.current = true;
    
    return () => {
      alive.current = false;
      
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  useEffect(() => {

    criticalRef.current = critical;
  }, [critical]);
  useEffect(() => {

    speedRef.current = SPEEDS[speed];
  }, [speed]);

  const tick = useCallback(async () => {

    const dried = Math.max(0, s.current.moisture - DRY_PER_STEP);

    try {
      const d = await api.demoDecide({

        moisture_pct: Math.round(dried * 10) / 10,
        reserve_ml: s.current.reserve,
        initial_reserve_ml: INITIAL_RESERVE_ML,
        critical_stage: criticalRef.current,
      });

      if (!alive.current) return;

      const newMoisture = Math.min(100, dried + d.delivered_ml * ABSORB_PER_ML);

      s.current.moisture = newMoisture;
      s.current.reserve = d.reserve_ml_after;
      s.current.step += 1;

      if (d.watered) s.current.waterings += 1;

      setMoisture(newMoisture);
      setReserve(d.reserve_ml_after);
      setStep(s.current.step);
      setWaterings(s.current.waterings);
      setPumpOn(d.watered);
      setReason(d.reason);
      setError(null);
      setHistory((h) => 
        [...h, { step: s.current.step, moisture: newMoisture, reserve: d.reserve_pct, watered: d.watered }].slice(
          -MAX_POINTS,
        ),
      );

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      stop();

      return;
    }
    if (runningRef.current && alive.current) {

      timer.current = window.setTimeout(tick, speedRef.current);
    }
  }, []);

  function start() {

    if (runningRef.current) return;

    runningRef.current = true;
    setRunning(true);
    timer.current = window.setTimeout(tick, 200);
  }

  function stop() {

    runningRef.current = false;
    setRunning(false);
    
    if (timer.current) window.clearTimeout(timer.current);
  }

  function reset() {
    stop();

    s.current = { moisture: START_MOISTURE, reserve: INITIAL_RESERVE_ML, step: 0, waterings: 0 };

    setMoisture(START_MOISTURE);
    setReserve(INITIAL_RESERVE_ML);
    setStep(0);
    setWaterings(0);
    setPumpOn(false);
    setCritical(false);
    setReason("Idle - press Start to run the demo.");
    setHistory([]);
    setError(null);
  }

  const reservePct = Math.round((reserve / INITIAL_RESERVE_ML) * 100);
  const exhausted = reserve <= 0;

  const chartOption: EChartsOption = {
    grid: { left: 44, right: 48, top: 28, bottom: 30 },
    legend: { data: ["Soil moisture %", "Reserve %"], top: 0 },
    tooltip: { trigger: "axis" },

    xAxis: { type: "category", data: history.map((p) => p.step), name: "step", nameLocation: "middle", nameGap: 22 },
    yAxis: [
      { type: "value", min: 0, max: 100, position: "left" },
      { type: "value", min: 0, max: 100, position: "right", axisLabel: { formatter: "{value}%" } },
    ],

    series: [
      {
        name: "Soil moisture %",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: history.map((p) => Math.round(p.moisture * 10) / 10),
        lineStyle: { width: 2, color: "#0a84ff" },
        areaStyle: { color: "rgba(10,132,255,0.10)" },

        markLine: {
          symbol: "none",
          data: [{ yAxis: critical ? 45 : 35, name: "trigger" }],
          lineStyle: { color: "#b7791f", type: "dashed" },
          label: { formatter: "trigger", color: "#b7791f" },
        },
      },
      {
        name: "Reserve %",
        type: "line",
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        data: history.map((p) => p.reserve),
        lineStyle: { width: 2, color: "#1a8a3c" },
      },
    ],
  };

  return (
    <>
      <div className="panel">
        <div className="titlebar">
          <span>Live Monitoring and Control</span>
          <span className="sub">software demo - no hardware needed</span>
        </div>
        <div className="panel-body">
          <div className="well">
            <p style={{ marginTop: 0 }}>
              This is the sense-decide-actuate loop running live. A simulated soil zone dries over time. The AquaReserve controller waters it from a finite reserve, protects it harder during a critical growth stage and stops once the reserve is spent. The same loop a real installed node runs and the same story the study quantifies.
            </p>

            <div className="controls" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
              <button className="enter-btn" onClick={running ? stop : start} style={{ minWidth: 96 }}>
                {running ? "Pause" : step === 0 ? "Start" : "Resume"}
              </button>
              <button onClick={reset}>Reset</button>
              <div className="field" style={{ minWidth: 120 }}>
                <label htmlFor="spd">Speed</label>
                <select id="spd" value={speed} onChange={(e) => setSpeed(e.target.value as keyof typeof SPEEDS)}>
                  {Object.keys(SPEEDS).map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>
              <label style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 14 }}>
                <input type="checkbox" checked={critical} onChange={(e) => setCritical(e.target.checked)} />
                Critical growth stage
              </label>
            </div>

            {error && (
              <p className="error" style={{ marginBottom: 0 }}>
                {error}
              </p>
            )}
          </div>

          <div className="kpis" style={{ marginTop: 14 }}>
            <div className="kpi">
              <div className="v">{moisture.toFixed(0)}%</div>
              <div className="l">Soil moisture</div>
            </div>
            <div className="kpi">
              <div className="v" style={{ color: exhausted ? "var(--ink-red)" : undefined }}>
                {reservePct}%
              </div>
              <div className="l">Reserve remaining ({reserve.toFixed(0)} ml)</div>
            </div>
            <div className="kpi">
              <div className="v">
                <span className={`badge ${pumpOn ? "green" : "red"}`}>{pumpOn ? "ON" : "OFF"}</span>
              </div>
              <div className="l">Pump</div>
            </div>
            <div className="kpi">
              <div className="v">{waterings}</div>
              <div className="l">Waterings (step {step})</div>
            </div>
          </div>

          <div style={{ marginTop: 14 }}>
            <MeterBar label="Soil moisture" pct={Math.round(moisture)} tone={level(moisture)} />
            <MeterBar label="Reserve" pct={reservePct} tone={level(reservePct)} />
          </div>

          <p className="muted" style={{ marginTop: 10 }}>
            Controller: <strong style={{ color: "var(--ink)" }}>{reason}</strong>
            {exhausted && " The reserve is empty, so the crop is now on its own - exactly the trade-off the study measures."}
          </p>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <div className="titlebar">
          <span>Soil moisture and reserve over time</span>
        </div>
        <div className="panel-body">
          {history.length === 0 ? (
            <p className="muted">Press Start to watch the controller spend the reserve to hold soil moisture at the trigger line.</p>
          ) : (
            <Chart option={chartOption} height={320} />
          )}
        </div>
      </div>
    </>
  );
}

function MeterBar({ label, pct, tone }: { label: string; pct: number; tone: "green" | "amber" | "red" }) {
  const color = tone === "green" ? "var(--ink-green)" : tone === "amber" ? "var(--ink-amber)" : "var(--ink-red)";
  
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--ink-soft)", marginBottom: 3 }}>
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div style={{ height: 12, borderRadius: 7, background: "rgba(0,0,0,0.07)", overflow: "hidden" }}>
        <div
          style={{
            width: `${Math.max(0, Math.min(100, pct))}%`,
            height: "100%",
            background: color,
            borderRadius: 7,
            transition: "width 0.35s ease",
          }}
        />
      </div>
    </div>
  );
}
