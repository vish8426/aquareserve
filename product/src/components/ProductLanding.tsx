// Marketing home for the customer product app.
// Sells the outcome and sends the visitor to the self-serve configurator.
// It is deliberately customer-facing, distinct from the results dashboard.
export default function ProductLanding({ onConfigure }: { onConfigure: () => void }) {

  return (
    <>
      <div className="panel">
        <div className="titlebar"><span>Save the Crop</span></div>
        <div className="panel-body">
          <div className="hero">
            <div className="hero-brand">
              <div className="big">Drought-Proof your Yield</div>
              <div className="tag">Smart Supplementary Irrigation</div>
              <div className="lede">
                AquaReserve spends a finite water reserve intelligently, to the right zone, at the right growth stage, so a drought does not cost you the harvest.<br />
                See your own sized system and payback in seconds.
              </div>
              <div style={{ marginTop: 18 }}>
                <button className="enter-btn" onClick={onConfigure}>Configure your System &rsaquo;</button>
              </div>
            </div>
            <div className="hero-render">
              <div className="well" style={{ textAlign: "left" }}>
                <div className="kpis">
                  <div className="kpi">
                    <div className="v">88%</div>
                    <div className="l">Onion yield held in the 2019 drought</div>
                  </div>
                  <div className="kpi">
                    <div className="v">&lt; 2 yr</div>
                    <div className="l">Typical payback</div>
                  </div>
                  <div className="kpi">
                    <div className="v">3x</div>
                    <div className="l">Production vs no system, under drought</div>
                  </div>
                </div>
              </div>
              <div className="hero-caption">Indicative from the AquaReserve simulation. Your numbers depend on your farm.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="titlebar"><span>How it works</span></div>
        <div className="panel-body">
          <div className="cols">
            <div className="col" onClick={onConfigure}>
              <h3>Size it</h3>
              <p>Tell us your crops and paddocks. We size the reserve and the hardware and price it.</p>
              <span className="go">Configure your System &rsaquo;</span>
            </div>
            <div className="col" onClick={onConfigure}>
              <h3>Prove it</h3>
              <p>See the yield protected and the payback before you spend a dollar, from a validated model.</p>
              <span className="go">See your Payback &rsaquo;</span>
            </div>
            <div className="col">
              <h3>Run it</h3>
              <p>Once installed, monitor and control your zones from anywhere. Live monitoring is coming soon.</p>
              <span className="go">Monitor (Coming Soon)</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
