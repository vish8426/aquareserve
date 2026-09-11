// Shared formatting helpers.
export const t1 = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 1 });
export const t0 = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

export function money(n: number, currency = "AUD") {
  return `${currency} ${t0(n)}`;
}

// Short labels for dense chart axes and legends, where the full labels collide.
export const CONTROLLER_SHORT: Record<string, string> = {
  rainfed: "Rainfed",
  fixed: "Fixed",
  threshold: "Threshold",
  smart_rule: "Smart-stage",
  mpc: "MPC",
  stochastic_mpc: "Robust MPC",
  rl_cem: "RL (CEM)",
  oracle: "Oracle",
};

// Palette: rainfed is grey (the "no system" baseline), the oracle is muted (unrealisable perfect foresight) and the deployable controllers get the accent blues/greens.
export const CONTROLLER_COLORS: Record<string, string> = {
  rainfed: "#9e9e9e",
  fixed: "#8d6e63",
  threshold: "#42a5f5",
  smart_rule: "#26a69a",
  mpc: "#1565c0",
  stochastic_mpc: "#5e35b1",
  rl_cem: "#ef6c00",
  oracle: "#78909c",
};
