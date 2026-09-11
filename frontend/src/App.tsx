import { useEffect, useState } from "react";
import { api } from "./api";
import ControllerComparison from "./components/ControllerComparison";
import Landing from "./components/Landing";
import ReserveSweep from "./components/ReserveSweep";
import RoiPanel from "./components/RoiPanel";
import TwinsPanel from "./components/TwinsPanel";
import { useAsync } from "./hooks";

type Tab = "comparison" | "reserve" | "economics" | "twin";
type View = "landing" | "app";

const TABS: { id: Tab; label: string }[] = [
  { id: "comparison", label: "Yield protection" },
  { id: "reserve", label: "Reserve sizing" },
  { id: "economics", label: "Economics" },
  { id: "twin", label: "Digital twin" },
];

export default function App() {
  const { value: meta, error, loading } = useAsync(() => api.meta(), []);
  const [view, setView] = useState<View>("landing");
  const [tab, setTab] = useState<Tab>("comparison");
  const [year, setYear] = useState<string>("severe");
  const [reserveMl, setReserveMl] = useState<number>(20);

  // default the reserve to the design size once meta arrives
  useEffect(() => {
    if (meta && !meta.reserve_sizes_ml.includes(reserveMl)) {
      setReserveMl(meta.design_reserve_ml);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta]);

  if (view === "landing")
    return (
      <Landing
        onEnter={(t) => {
          if (t) setTab(t as Tab);
          setView("app");
        }}
      />
    );

  if (loading) return <div className="app"><div className="status">Loading dashboard...</div></div>;
  if (error || !meta)
    return (
      <div className="app">
        <div className="panel">
          <div className="titlebar"><span>AquaReserve</span></div>
          <div className="panel-body status error">
            Could not load the results store.<br />
            {error}
            <p className="muted">
              Generate it with <code>python scripts/run_matrix.py</code> and start the API with{" "}
              <code>uvicorn backend.app.main:app</code>.
            </p>
          </div>
        </div>
      </div>
    );

  const showControls = tab !== "twin";

  return (
    <div className="app">
      <header className="masthead">
        <div className="brandrow">
          <div className="brand">
            Aqua<span className="drop">Reserve</span>
          </div>
          <div className="brandtag">Smart Supplementary-Irrigation Digital Twin</div>
          <a className="home-link" href="#" onClick={(e) => { e.preventDefault(); setView("landing"); }}>
            Home
          </a>
        </div>
        <div className="masthead-sub">
          <strong>{meta.farm}</strong> - {meta.region}.<br />
          Protecting {meta.zones.map((z) => `${z.crop} ${z.area_ha} ha`).join(", ")} from drought with a finite {meta.reserve_capacity_ml} ML water reserve.<br />
          All figures are precomputed engine output.
        </div>
      </header>

      <nav className="navband">
        <div className="tabs">
          {TABS.map((t) => (
            <div
              key={t.id}
              className={`tab ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </div>
          ))}
        </div>
      </nav>

      {showControls && (
        <div className="toolbar">
          <div className="controls">
            <div className="field">
              <label htmlFor="year">Season</label>
              <select id="year" value={year} onChange={(e) => setYear(e.target.value)}>
                {meta.years.map((y) => (
                  <option key={y.id} value={y.id}>{y.label}</option>
                ))}
              </select>
            </div>
            {tab !== "reserve" && (
              <div className="field">
                <label htmlFor="reserve">Reserve size (ML)</label>
                <select
                  id="reserve"
                  value={reserveMl}
                  onChange={(e) => setReserveMl(Number(e.target.value))}
                >
                  {meta.reserve_sizes_ml.map((s) => (
                    <option key={s} value={s}>{s} ML{s === meta.design_reserve_ml ? " (design)" : ""}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "comparison" && <ControllerComparison meta={meta} year={year} reserveMl={reserveMl} />}
      {tab === "reserve" && <ReserveSweep meta={meta} year={year} />}
      {tab === "economics" && <RoiPanel reserveMl={reserveMl} />}
      {tab === "twin" && <TwinsPanel />}

      <footer>
        AquaReserve - Simulation-only digital twin. Data served read-only from the precomputed results store.
      </footer>
    </div>
  );
}
