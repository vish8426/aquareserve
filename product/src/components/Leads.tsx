import { api, type Lead } from "../api";
import { useAsync } from "../hooks";

// Saved quotes list.
// Customers see their own; the admin sees all.
export default function Leads({ admin }: { admin: boolean }) {
  const { value, error, loading } = useAsync<Lead[]>(() => (admin ? api.adminLeads() : api.myLeads()), [admin]);

  const num = (v: unknown) => (typeof v === "number" ? v : undefined);
  const money = (v: unknown) => {
    const n = num(v);
    
    return n === undefined ? "-" : `AUD ${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  };

  return (
    <div className="panel">
      <div className="titlebar">
        <span>{admin ? "All saved quotes (admin)" : "My saved quotes"}</span>
      </div>
      <div className="panel-body">
        {loading && <div className="status">Loading...</div>}
        {error && <div className="status error">{error}</div>}
        {value && value.length === 0 && (
          <div className="well muted">No saved quotes yet. Configure a system and choose Save this quote.</div>
        )}
        {value && value.length > 0 && (
          <div className="well" style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Saved</th>
                  {admin && <th>Account</th>}
                  <th>Contact</th>
                  <th>Farm</th>
                  <th>Reserve</th>
                  <th>Capex</th>
                  <th>Payback</th>
                </tr>
              </thead>
              <tbody>
                {value.map((ld) => (
                  <tr key={ld.id}>
                    <td>{ld.created?.replace("T", " ").replace("Z", "")}</td>
                    {admin && <td>{ld.user?.email ?? "-"}</td>}
                    <td>{ld.contact?.name ?? "-"}{ld.contact?.email ? ` (${ld.contact.email})` : ""}</td>
                    <td>{ld.contact?.farm ?? ld.profile?.region ?? "-"}</td>
                    <td>{num(ld.summary?.reserve_ml) ?? "-"} ML</td>
                    <td>{money(ld.summary?.capex_aud)}</td>
                    <td>{num(ld.summary?.payback_years) ?? "-"} yr</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
