import { useState } from "react";

// Digital-twin tab: embeds the two self-contained viewers the backend serves at /twins.
// They replay the same engine output the dashboard charts summarise, so the numbers agree.
export default function TwinsPanel() {
  const [view, setView] = useState<"2d" | "3d">("2d");
  const src = view === "2d" ? "/twins/farm_twin.html" : "/twins/farm_twin_3d.html";

  return (
    <div className="panel">
      <div className="titlebar">
        <span>Digital twin</span>
        <span className="sub">top-down 2D and 3D playback</span>
      </div>
      <div className="panel-body">
        <div className="controls" style={{ marginBottom: 10 }}>
          <button onClick={() => setView("2d")} style={{ fontWeight: view === "2d" ? "bold" : "normal" }}>
            2D top-down
          </button>
          <button onClick={() => setView("3d")} style={{ fontWeight: view === "3d" ? "bold" : "normal" }}>
            3D field
          </button>
          <a href={src} target="_blank" rel="noreferrer" style={{ alignSelf: "center" }}>
            open in a new tab
          </a>
        </div>
        <iframe className="twin-frame" src={src} title={`AquaReserve ${view} twin`} />
        <p className="muted" style={{ marginBottom: 0 }}>
          Both viewers replay real per-day engine output. Use the controls inside the viewer to switch controller and season and to scrub the timeline.
        </p>
      </div>
    </div>
  );
}
