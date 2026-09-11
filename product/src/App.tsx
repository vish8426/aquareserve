import { useEffect, useState } from "react";
import { api, type User } from "./api";
import AuthGate from "./components/AuthGate";
import Configurator from "./components/Configurator";
import Leads from "./components/Leads";
import Monitor from "./components/Monitor";
import ProductLanding from "./components/ProductLanding";
import { useAsync } from "./hooks";

// AquaReserve customer product app, gated by login.
// Separate from the results dashboard.
// Reads the same backend API.
// Pages: a marketing home, the configurator, a Monitor placeholder, the user's saved quotes and an admin view of all quotes.
type Page = "home" | "configure" | "monitor" | "quotes" | "admin";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [page, setPage] = useState<Page>("home");
  const { value: meta } = useAsync(() => api.meta(), []);

  useEffect(() => {

    if (api.hasToken()) {

      api.me().then(setUser).catch(() => api.logout()).finally(() => setAuthReady(true));
    } else {

      setAuthReady(true);
    }
  }, []);

  if (!authReady) return <div className="app"><div className="panel"><div className="panel-body status">Loading...</div></div></div>;
  if (!user) return <AuthGate onAuthed={setUser} />;

  const nav: { id: Page; label: string }[] = [
    { id: "home", label: "Home" },
    { id: "configure", label: "Configure" },
    { id: "monitor", label: "Monitor" },
    { id: "quotes", label: "My Quotes" },
  ];
  
  if (user.role === "admin") nav.push({ id: "admin", label: "Admin" });

  function logout() {
    api.logout();
    setUser(null);
    setPage("home");
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="brandrow">
          <div className="brand">Aqua<span className="drop">Reserve</span></div>
          <div className="brandtag">Protect your crop from drought</div>
          <span className="home-link">
            {user.email}{user.role === "admin" ? " (admin)" : ""} &middot;{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}>Sign out</a>
          </span>
        </div>
      </header>

      <nav className="navband">
        <div className="tabs">
          {nav.map((n) => (
            <div key={n.id} className={`tab ${page === n.id ? "active" : ""}`} onClick={() => setPage(n.id)}>
              {n.label}
            </div>
          ))}
        </div>
      </nav>

      {page === "home" && <ProductLanding onConfigure={() => setPage("configure")} />}
      {page === "configure" && (
        meta ? <Configurator meta={meta} /> : <div className="panel"><div className="panel-body status">Loading...</div></div>
      )}
      {page === "monitor" && <Monitor />}
      {page === "quotes" && <Leads admin={false} />}
      {page === "admin" && user.role === "admin" && <Leads admin={true} />}

      <footer>
        AquaReserve - smart supplementary irrigation. Indicative figures for planning; not a firm quote.
      </footer>
    </div>
  );
}
