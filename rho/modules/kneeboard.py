"""
Rho — kneeboard PDF generator

Generates a compact, printable kneeboard card for a VFR cross-country flight.
Uses reportlab (platypus).  No external fonts required.

Usage:
    from rho.modules.kneeboard import generate_kneeboard
    pdf_bytes = generate_kneeboard(brief, comms_o, comms_d)
    # pdf_bytes is a bytes object — pass directly to st.download_button
"""

import io
import math
from datetime import date as _date

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, Image,
)

# ── Colour palette ─────────────────────────────────────────────────────────────
_NAVY   = colors.HexColor("#1e293b")
_BLUE   = colors.HexColor("#1e40af")
_GREEN  = colors.HexColor("#15803d")
_YELLOW = colors.HexColor("#a16207")
_RED    = colors.HexColor("#b91c1c")
_LIGHT  = colors.HexColor("#f8fafc")
_BORDER = colors.HexColor("#e2e8f0")
_GRAY   = colors.HexColor("#64748b")

# ── Styles ─────────────────────────────────────────────────────────────────────
_base = getSampleStyleSheet()

_H1 = ParagraphStyle("H1", parent=_base["Normal"],
                     fontSize=14, textColor=colors.white,
                     fontName="Helvetica-Bold", alignment=TA_CENTER)
_H2 = ParagraphStyle("H2", parent=_base["Normal"],
                     fontSize=10, textColor=colors.white,
                     fontName="Helvetica-Bold", alignment=TA_LEFT)
_H3 = ParagraphStyle("H3", parent=_base["Normal"],
                     fontSize=9, textColor=_NAVY,
                     fontName="Helvetica-Bold")
_BODY = ParagraphStyle("BODY", parent=_base["Normal"],
                       fontSize=8, textColor=_NAVY,
                       fontName="Helvetica", leading=11)
_SMALL = ParagraphStyle("SMALL", parent=_base["Normal"],
                        fontSize=7, textColor=_GRAY,
                        fontName="Helvetica", leading=9)
_MONO = ParagraphStyle("MONO", parent=_base["Normal"],
                       fontSize=7, textColor=_NAVY,
                       fontName="Courier", leading=9)


def _section_header(title, bg=_NAVY):
    """Coloured section banner."""
    tbl = Table([[Paragraph(title, _H2)]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _kv_table(rows, col_w=(1.2 * inch, 4.8 * inch)):
    """Two-column key/value table."""
    data = [[Paragraph(k, _SMALL), Paragraph(v, _BODY)] for k, v in rows]
    tbl = Table(data, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.25, _BORDER),
        ("BACKGROUND",    (0, 0), (0, -1), _LIGHT),
    ]))
    return tbl


def _wx_block(icao, assess, comms):
    """Weather + comms block for one airport."""
    cat      = assess.get("category", "?")
    cat_clr  = {"VFR": _GREEN, "MVFR": _YELLOW, "IFR": _RED, "LIFR": _RED}.get(cat, _GRAY)
    cat_style = ParagraphStyle("CAT", parent=_H3, textColor=cat_clr)

    rows = []

    # Flight category
    rows.append(("Category", f"<b><font color='#{cat_clr.hexval()[2:]}'>{cat}</font></b>"))

    # Winds
    wd = assess.get("wind_dir"); wk = assess.get("wind_kt")
    if wd is not None and wk is not None:
        rows.append(("Winds", f"{wd:03d}° @ {wk} kt"))

    # Active runway
    rwy = assess.get("best_runway")
    xw  = assess.get("crosswind_kt")
    if rwy:
        xw_str = f"  ({xw:.0f} kt XW)" if xw else ""
        rows.append(("Runway", f"{rwy}{xw_str}"))

    # Sky / ceiling
    sky = assess.get("sky_conditions", "CLR")
    rows.append(("Sky", sky))
    if assess.get("ceiling_ft"):
        rows.append(("Ceiling", f"{assess['ceiling_ft']:,} ft AGL"))

    # Vis
    if assess.get("visibility") is not None:
        rows.append(("Visibility", f"{assess['visibility']} sm"))

    # Temp / dew
    tc = assess.get("temp_c"); dc = assess.get("dewpoint_c")
    if tc is not None:
        t_str = f"{tc}°C"
        if dc is not None:
            spread = tc - dc
            t_str += f"  /  Dew {dc}°C  (T/D {spread}°C)"
        rows.append(("Temp", t_str))

    # Altimeter
    alt = assess.get("altimeter")
    if alt:
        try:
            rows.append(("Altimeter", f'{float(alt):.2f}" Hg'))
        except (ValueError, TypeError):
            rows.append(("Altimeter", str(alt)))

    # Comms
    freq_parts = []
    if comms.get("atis"):   freq_parts.append(f"ATIS {comms['atis']}")
    if comms.get("tower"):  freq_parts.append(f"TWR {comms['tower']}")
    if comms.get("ground"): freq_parts.append(f"GND {comms['ground']}")
    if comms.get("unicom"): freq_parts.append(f"UNICOM {comms['unicom']}")
    if comms.get("ctaf"):   freq_parts.append(f"CTAF {comms['ctaf']}")
    if comms.get("approach"):
        seen = set()
        for a in comms["approach"]:
            freq = (a.get("freq") or "").strip()
            try:
                freq_f = float(freq.split()[0].replace(";", ""))
            except (ValueError, IndexError):
                continue
            clean = freq.split()[0]
            if clean not in seen and freq_f < 136:
                freq_parts.append(f"APP {clean}")
                seen.add(clean)
                break
    if freq_parts:
        rows.append(("Comms", "  |  ".join(freq_parts)))

    # Raw METAR
    raw = assess.get("raw_metar")
    if raw:
        rows.append(("METAR", raw[:80] + ("..." if len(raw) > 80 else "")))

    header_bg = {"VFR": _GREEN, "MVFR": _YELLOW, "IFR": _RED, "LIFR": _RED}.get(cat, _NAVY)
    elements  = [
        _section_header(f"  {icao}  —  {cat}", bg=header_bg),
        Spacer(1, 2),
        _kv_table(rows),
        Spacer(1, 4),
    ]
    return elements


def _generate_route_map(o_lat, o_lon, d_lat, d_lon,
                        origin_icao, dest_icao,
                        airspaces=None, cruise_alt_ft=3500,
                        width_in=6.5, height_in=2.8):
    """Route map via map_utils (contextily tiles or plain fallback). Print-friendly (light)."""
    try:
        from rho.modules.map_utils import generate_route_map_png
        return generate_route_map_png(
            o_lat, o_lon, d_lat, d_lon,
            origin_icao, dest_icao,
            airspaces=airspaces,
            cruise_alt_ft=cruise_alt_ft,
            width_in=width_in, height_in=height_in,
            dark=False,
        )
    except Exception:
        return None


def generate_kneeboard(brief, comms_o, comms_d, aircraft=None):
    """
    Generate a kneeboard PDF from a pre-flight brief dict and comms dicts.

    Parameters
    ----------
    brief    : dict from insights.get_preflight_brief()
    comms_o  : dict from comms.get_comms(origin)
    comms_d  : dict from comms.get_comms(dest)
    aircraft : dict from aircraft.get_aircraft() or None — adds V-speeds section

    Returns
    -------
    bytes — PDF file contents, ready for st.download_button
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch,  bottomMargin=0.5 * inch,
    )

    story = []
    W     = letter[0] - inch  # usable width

    origin = brief.get("origin_icao", "???")
    dest   = brief.get("dest_icao",   "???")
    rec    = brief.get("recommendation", "—")
    reason = brief.get("reason", "")
    o_ass  = brief.get("origin_assess") or {}
    d_ass  = brief.get("dest_assess")   or {}
    route  = brief.get("route") or {}
    hazards = brief.get("hazards") or []

    rec_clr = {"GO": _GREEN, "CAUTION": _YELLOW, "NO-GO": _RED}.get(rec, _GRAY)

    # ── Title bar ─────────────────────────────────────────────────────────────
    title_data = [[
        Paragraph("RHO  —  VFR KNEEBOARD", _H1),
        Paragraph(f"{origin} → {dest}", _H1),
        Paragraph(str(_date.today()), _H1),
    ]]
    title_tbl = Table(title_data, colWidths=[W * 0.4, W * 0.35, W * 0.25])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 6))

    # ── Go/No-Go banner ───────────────────────────────────────────────────────
    nogo_style = ParagraphStyle("NOGO", parent=_H1,
                                textColor=colors.white, fontSize=12,
                                alignment=TA_LEFT)
    nogo_data  = [[Paragraph(f"  {rec}  —  {reason}", nogo_style)]]
    nogo_tbl   = Table(nogo_data, colWidths=[W])
    nogo_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), rec_clr),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(nogo_tbl)
    story.append(Spacer(1, 6))

    # ── Route summary vars (used by both map and summary table) ──────────────
    direct  = route.get("direct") or {}
    dist_nm = direct.get("distance_nm")
    pens    = direct.get("airspace_penetrations") or []
    alt_ft  = brief.get("cruise_alt_ft", "—")

    # ── Route map ─────────────────────────────────────────────────────────────
    o_apt = brief.get("origin_apt") or {}
    d_apt = brief.get("dest_apt")   or {}
    o_lat = o_apt.get("lat"); o_lon = o_apt.get("lon")
    d_lat = d_apt.get("lat"); d_lon = d_apt.get("lon")

    if all(v is not None for v in [o_lat, o_lon, d_lat, d_lon]):
        map_png = _generate_route_map(
            o_lat, o_lon, d_lat, d_lon, origin, dest,
            airspaces=brief.get("airspaces"),
            cruise_alt_ft=brief.get("cruise_alt_ft", 3500),
            width_in=W / inch, height_in=2.6,
        )
        if map_png:
            map_img = Image(io.BytesIO(map_png), width=W, height=2.6 * inch)
            story.append(map_img)
            story.append(Spacer(1, 4))

    route_rows = []
    if dist_nm:
        route_rows.append(("Distance", f"{dist_nm} nm direct"))
    route_rows.append(("Cruise Alt", f"{alt_ft} ft MSL"))
    if pens:
        pen_str = ";  ".join(
            f"Class {p['class']}: {p['name']} ({p['lower']}–{p['upper']})"
            for p in pens[:4]
        )
        route_rows.append(("Airspace", pen_str))
    else:
        route_rows.append(("Airspace", "No controlled airspace conflicts on direct route"))

    story.append(KeepTogether([
        _section_header("  ROUTE"),
        Spacer(1, 2),
        _kv_table(route_rows, col_w=(1.2 * inch, W - 1.2 * inch)),
        Spacer(1, 8),
    ]))

    # ── Weather: side-by-side ─────────────────────────────────────────────────
    o_els = _wx_block(origin, o_ass, comms_o)
    d_els = _wx_block(dest,   d_ass, comms_d)

    # Wrap each side in a single-cell table, then combine side by side
    def _wrap(elements, width):
        inner = [[e] for e in elements]
        tbl = Table(inner, colWidths=[width])
        tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        return tbl

    half = (W - 6) / 2
    side_by_side = Table(
        [[_wrap(o_els, half), _wrap(d_els, half)]],
        colWidths=[half + 3, half + 3],
    )
    side_by_side.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("LINEAFTER",    (0, 0), (0, -1), 0.5, _BORDER),
    ]))
    story.append(side_by_side)
    story.append(Spacer(1, 8))

    # ── Hazards ───────────────────────────────────────────────────────────────
    if hazards:
        hazard_els = [
            _section_header("  HAZARDS & ADVISORIES", bg=_RED),
            Spacer(1, 2),
        ]
        for h in hazards[:8]:
            hazard_els.append(Paragraph(f"- {h}", _BODY))
            hazard_els.append(Spacer(1, 2))
        story.append(KeepTogether(hazard_els + [Spacer(1, 8)]))

    # ── Emergency reference ───────────────────────────────────────────────────
    emg_rows = [
        ("Guard freq",      "121.5 MHz — monitor in flight"),
        ("Emergency xpdr",  "7700 = Emergency   7600 = Comms failure   7500 = Hijack"),
        ("Lost comms",      "Squawk 7600, attempt contact on last assigned, then 121.5"),
        ("Emergency ldg",   "Best glide → mayday on 121.5 → pick field → ABCDE checklist"),
        ("ABCDE",           "Airspeed (best glide)  |  Best field  |  Checklist  |  Declare  |  Execute"),
    ]
    story.append(KeepTogether([
        _section_header("  EMERGENCY REFERENCE", bg=colors.HexColor("#7c1d6f")),
        Spacer(1, 2),
        _kv_table(emg_rows, col_w=(1.2 * inch, W - 1.2 * inch)),
        Spacer(1, 8),
    ]))

    # ── V-speeds reference (if aircraft provided) ─────────────────────────────
    if aircraft:
        vs_rows = [
            ("Aircraft", aircraft["display"]),
            ("V-speeds",
             f"Vg {aircraft['vg']} kt  |  Vx {aircraft['vx']} kt  |  "
             f"Vy {aircraft['vy']} kt  |  Vs0 {aircraft['vs0']} kt  |  "
             f"Vs1 {aircraft['vs1']} kt  |  Va {aircraft['va']} kt"),
            ("Vno / Vne",
             f"{aircraft['vno']} kt max structural cruise  |  {aircraft['vne']} kt never exceed"),
            ("Fuel",
             f"{aircraft['fuel_usable_gal']} gal usable  |  {aircraft['fuel_burn_gph']} gph  |  "
             f"Oil cap: {aircraft['oil_capacity_qt']} qt"),
        ]
        story.append(KeepTogether([
            _section_header("  AIRCRAFT V-SPEEDS"),
            Spacer(1, 2),
            _kv_table(vs_rows, col_w=(1.2 * inch, W - 1.2 * inch)),
            Spacer(1, 8),
        ]))

    # ── Pre-departure checklist ───────────────────────────────────────────────
    checklist_items = [
        ("ATIS / AWOS",    "Obtain current ATIS, set altimeter, note active runway"),
        ("Fuel",           "Verify quantity — VFR day: dest + 30 min reserve (61.23)"),
        ("W&B",            "Check weight and balance within limits for planned fuel + pax"),
        ("NOTAMs",         "Check for runway/airspace NOTAMs at origin and destination"),
        ("Flight plan",    "File VFR flight plan if XC — activate with ATC before departure"),
        ("Squawk",         "Set transponder to 1200 unless ATC assigns code"),
        ("Radio check",    "Test comms on ground freq before taxi"),
        ("Run-up",         "Magnetos (+/- 125 RPM max drop, 50 RPM max diff), carb heat, controls"),
        ("Takeoff brief",  "Abort criteria, engine failure plan (first 500 ft, above 500 ft)"),
    ]
    story.append(KeepTogether([
        _section_header("  PRE-DEPARTURE CHECKLIST"),
        Spacer(1, 2),
        _kv_table(checklist_items, col_w=(1.2 * inch, W - 1.2 * inch)),
        Spacer(1, 8),
    ]))

    # ── In-flight notes box ────────────────────────────────────────────────────
    lines_data = [[Paragraph("IN-FLIGHT NOTES", _H2)]]
    lines_tbl  = Table(lines_data, colWidths=[W])
    lines_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(lines_tbl)

    note_rows = [[""] for _ in range(10)]
    note_tbl  = Table(note_rows, colWidths=[W])
    note_tbl.setStyle(TableStyle([
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(note_tbl)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by Rho  •  {_date.today()}  •  For training use only — always verify with official sources",
        _SMALL,
    ))

    doc.build(story)
    return buf.getvalue()
