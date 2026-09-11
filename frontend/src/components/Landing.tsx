import InstallScene3D from "./InstallScene3D";

// Landing page in the spirit of the home page: a 3D product "render" of the full install, a hot-news bar and three product columns.
// The render is a bundled Three.js scene standing in for the iMac hero shot.
export default function Landing({ onEnter }: { onEnter: (tab?: string) => void }) {
  return (
    <div className="app landing">
      <div className="hero">
        <div className="hero-brand">
          <div className="big">Aqua<span className="drop">Reserve</span></div>
          <div className="tag">save the crop.</div>
          <div className="lede">
            A simulation-only smart supplementary irrigation digital twin.<br />
            It manages a finite water reserve to protect crop yield through drought and proves the case before a farmer spends a dollar.
          </div>
        </div>
        <div className="hero-render">
          <InstallScene3D />
          <div className="hero-caption"></div>
        </div>
      </div>

      <p className="dateline">Mallee Mixed Demonstration Farm - Mildura, Victoria. Simulation Edition.</p>

      <div className="hotnews">
        <div className="htag">Field Report</div>
        <div className="headline">
          AquaReserve holds onion at 88% of full yield through the real 2019 drought while the rainfed field fails at 15%.
        </div>
      </div>

      <div className="cols">
        <div className="col" onClick={() => onEnter("comparison")}>
          <div className="icon">
            <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
              <path d="M20 4 C12 16 8 22 8 28 a12 12 0 0 0 24 0 C32 22 28 16 20 4 Z" fill="#3f7bb0" stroke="#22456e" strokeWidth="1.5" />
              <path d="M20 30 l-3 -3 3 -3 3 3 z" fill="#fff" />
            </svg>
          </div>
          <h3>Protect</h3>
          <p>Drip and sprinkler that carry crops through drought - onion held at 88% of full yield in 2019.</p>
          <span className="go">See yield protection &rsaquo;</span>
        </div>
        <div className="col" onClick={() => onEnter("twin")}>
          <div className="icon">
            <svg width="44" height="40" viewBox="0 0 44 40" aria-hidden="true">
              <rect x="4" y="4" width="36" height="24" rx="2" fill="#dcdcdc" stroke="#444" strokeWidth="1.5" />
              <rect x="7" y="7" width="30" height="18" fill="#1f5136" />
              <rect x="18" y="28" width="8" height="5" fill="#9a9a8f" />
              <rect x="12" y="33" width="20" height="3" fill="#6a6a60" />
            </svg>
          </div>
          <h3>See</h3>
          <p>A living digital twin of the farm - watch the reserve drain and the fields hold, in 2D and 3D.</p>
          <span className="go">Open the twin &rsaquo;</span>
        </div>
        <div className="col" onClick={() => onEnter("economics")}>
          <div className="icon">
            <svg width="44" height="40" viewBox="0 0 44 40" aria-hidden="true">
              <line x1="6" y1="34" x2="40" y2="34" stroke="#444" strokeWidth="1.5" />
              <rect x="9" y="22" width="7" height="12" fill="#42a5f5" />
              <rect x="19" y="14" width="7" height="20" fill="#1f7a34" />
              <rect x="29" y="8" width="7" height="26" fill="#c8791a" />
            </svg>
          </div>
          <h3>Prove</h3>
          <p>A payback under two years and a positive ten-year NPV, straight from the model.</p>
          <span className="go">Run the numbers &rsaquo;</span>
        </div>
      </div>

      <div className="enter-wrap">
        <button className="enter-btn" onClick={() => onEnter("comparison")}>Enter the Dashboard</button>
      </div>

      <footer>
        AquaReserve - Simulation-only digital twin. All figures are precomputed engine output.
      </footer>
    </div>
  );
}
