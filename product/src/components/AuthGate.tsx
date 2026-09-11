import { useState } from "react";
import { api, type User } from "../api";

// Login / register gate for the product app.
// The whole product app sits behind this.
// Customers self-register; the admin account is seeded server-side.
export default function AuthGate({ onAuthed }: { onAuthed: (u: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [farm, setFarm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);

    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }

    if (mode === "register" && !name.trim()) {
      setError("Your name is required.");
      return;
    }

    setBusy(true);
    
    try {
      const user =
        mode === "login"
          ? await api.login({ email: email.trim(), password })
          : await api.register({ email: email.trim(), password, name: name.trim(), farm: farm.trim() || undefined });
      onAuthed(user);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="brandrow">
          <div className="brand">Aqua<span className="drop">Reserve</span></div>
          <div className="brandtag">Protect your crop from drought</div>
        </div>
      </header>

      <div className="panel" style={{ maxWidth: 460, margin: "0 auto" }}>
        <div className="titlebar">
          <span>{mode === "login" ? "Sign in" : "Create your account"}</span>
        </div>
        <div className="panel-body">
          <div className="well">
            {mode === "register" && (
              <div className="field" style={{ marginBottom: 10 }}>
                <label htmlFor="an">Your name</label>
                <input id="an" type="text" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            )}
            {mode === "register" && (
              <div className="field" style={{ marginBottom: 10 }}>
                <label htmlFor="af">Farm (optional)</label>
                <input id="af" type="text" value={farm} onChange={(e) => setFarm(e.target.value)} />
              </div>
            )}
            <div className="field" style={{ marginBottom: 10 }}>
              <label htmlFor="ae">Email</label>
              <input id="ae" type="text" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field" style={{ marginBottom: 12 }}>
              <label htmlFor="ap">Password{mode === "register" ? " (at least 8 characters)" : ""}</label>
              <input id="ap" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()} />
            </div>
            <button className="enter-btn" onClick={submit} disabled={busy}>
              {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
            {error && <p className="error" style={{ margin: "10px 0 0" }}>{error}</p>}
            <p className="muted" style={{ margin: "12px 0 0" }}>
              {mode === "login" ? "New to AquaReserve? " : "Already have an account? "}
              <a href="#" onClick={(e) => { e.preventDefault(); setError(null); setMode(mode === "login" ? "register" : "login"); }}>
                {mode === "login" ? "Create an account" : "Sign in"}
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
