"""One-page system proposal PDF

Turns a configurator result into a customer-ready proposal: the farm, the recommended system, the estimated drought outcome, the investment case and the hardware quote.
Built with fpdf2, so it renders anywhere without system libraries.
This doubles as the handover-pack seed.
"""

from __future__ import annotations

from datetime import date

from fpdf import FPDF

GREEN = (31, 81, 54)
INK = (26, 26, 26)
GREY = (110, 110, 115)
LINE = (200, 200, 195)


def _money(v: float, cur: str) -> str:
    return f"{cur} {v:,.0f}"


class _Doc(FPDF):
    def header(self) -> None:  # noqa: D401 - fpdf hook
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*GREEN)
        self.cell(0, 10, "AquaReserve", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 12)
        self.set_text_color(*INK)
        self.cell(0, 7, "System Proposal", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*GREEN)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)

    def footer(self) -> None:  # noqa: D401 - fpdf hook
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.multi_cell(
            0, 4,
            "Indicative for planning only, not a firm quote." 
            "Figures are precomputed AquaReserve simulation output and depend on the farm details provided." 
            "Confirm with a supplier and an installer before purchase.",
            )


def _section(pdf: _Doc, title: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)


def _kv(pdf: _Doc, key: str, value: str) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(70, 6, key)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")


def build_proposal_pdf(profile: dict, result: dict) -> bytes:
    d, o, e = result["design"], result["outcome"], result["economics"]
    cur = e["currency"]
    pdf = _Doc(format="A4")
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, f"Prepared {date.today().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)

    # your farm
    _section(pdf, "Your farm")
    region = profile.get("region", "your region")
    zones = profile.get("zones", [])
    _kv(pdf, "Region", str(region))
    for z in zones:
        irr = z.get("irrigation") or "-"
        _kv(pdf, f"Zone - {z['crop']}", f"{z['area_ha']} ha, {irr}")

    # recommended system
    _section(pdf, "Recommended system")
    _kv(pdf, "Water reserve", f"{d['reserve_ml']} ML ({d.get('reserve_basis', 'recommended')})")
    _kv(pdf, "Control zones", str(d["zones"]))
    _kv(pdf, "Controller", "Model Predictive Control (MPC)")
    lic = result.get("licence") or {}
    if lic.get("capped"):
        forgone = lic.get("forgone_production_t")
        note = (
            f"Reserve held to your {lic['cap_ml']:g} ML water licence. The NPV-optimal size would be "
            f"{lic['uncapped_reserve_ml']} ML"
            + (f", forgoing about {forgone} t of drought-year production" if forgone else "")
            + "; a larger entitlement would allow more protection."
        )
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 5, note)
        pdf.set_text_color(*INK)

    # outcome
    _section(pdf, "Estimated outcome (severe drought)")
    _kv(pdf, "Production with AquaReserve", f"{o['production_t']} t")
    _kv(pdf, "Production rainfed (no system)", f"{o['rainfed_t']} t")
    _kv(pdf, "Yield protected", f"+{o['yield_protected_pct']:.0f}%")
    _kv(pdf, "Water used from reserve", f"{o['water_used_ml']} ML")
    _kv(pdf, "Reserve survival", f"{o['reserve_survival_days']} days")
    market = ", ".join(
        f"{c} {round(v['relative_yield'] * 100)}% ({'marketable' if v['marketable'] else 'at risk'})"
        for c, v in o["crops"].items()
    )
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 5, f"Per crop: {market}")
    pdf.set_text_color(*INK)

    # investment
    _section(pdf, "Investment")
    _kv(pdf, "System capex", _money(d["capex_aud"], cur))
    pb = e.get("payback_range_years")
    pb_txt = f"{e['payback_years']} yr" if e.get("payback_years") else "-"
    if pb:
        pb_txt += f" (range {pb[0]}-{pb[1]})"
    _kv(pdf, "Payback", pb_txt)
    _kv(pdf, f"Net present value ({e['horizon_years']}-yr)", _money(e["npv_aud"], cur))
    _kv(pdf, "Equipment-as-a-service", f"{_money(e['monthly_eaas_aud'], cur)} / month")

    # hardware quote
    _section(pdf, "Hardware and quote")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(236, 234, 221)
    pdf.set_draw_color(*LINE)
    widths = [96, 34, 16, 34]
    for w, h in zip(widths, ["Item", "Type", "Qty", "Total"], strict=True):
        pdf.cell(w, 6, h, border=1, fill=True, align="L" if h == "Item" else "R")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for item in d["hardware"]:
        pdf.cell(widths[0], 6, str(item["item"])[:58], border=1)
        pdf.cell(widths[1], 6, str(item["type"]), border=1, align="R")
        pdf.cell(widths[2], 6, str(item["qty"]), border=1, align="R")
        pdf.cell(widths[3], 6, _money(item["total"], cur), border=1, align="R")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(sum(widths[:3]), 6, "Capex", border=1, align="R")
    pdf.cell(widths[3], 6, _money(d["capex_aud"], cur), border=1, align="R")
    pdf.ln()

    out = pdf.output()
    return bytes(out)
