"""
Rho — In-Flight Cheat Sheet

A one-page, flight-order reference card for use DURING the flight.
Organized exactly as the flight unfolds:

  DEPARTURE (comms, runway, initial heading)
  → EN ROUTE (airspace in crossing order, with rules + frequencies)
  → ARRIVAL (comms, runway, pattern)
  + EMERGENCY strip at bottom

Not a pre-flight brief — weather analysis stays in the brief.
Only what the student needs to reference mid-flight.
"""

import io
import math
from datetime import date as _date

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable,
)

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY    = colors.HexColor("#1e293b")
_BLUE    = colors.HexColor("#1e40af")
_TEAL    = colors.HexColor("#0e7490")
_GREEN   = colors.HexColor("#15803d")
_AMBER   = colors.HexColor("#b45309")
_RED     = colors.HexColor("#991b1b")
_PURPLE  = colors.HexColor("#6d28d9")
_SLATE   = colors.HexColor("#475569")
_LIGHT   = colors.HexColor("#f1f5f9")
_BORDER  = colors.HexColor("#cbd5e1")
_WHITE   = colors.white

# ── Airspace class rules ──────────────────────────────────────────────────────
_AIRSPACE = {
    "B": {
        "label": "Class B  (Bravo)",
        "color": _BLUE,
        "contact": "~30 nm out — Approach Control",
        "rule":    "ATC CLEARANCE REQUIRED — must receive 'Cleared into the Bravo'. No entry without it.",
        "mins":    "3 sm vis, clear of clouds inside Bravo.",
    },
    "C": {
        "label": "Class C  (Charlie)",
        "color": _PURPLE,
        "contact": "~10-15 nm out — Approach Control",
        "rule":    "Two-way radio CONTACT required before entering. ATC must acknowledge your callsign. "
                   "They don't have to clear you — contact alone is enough.",
        "mins":    "3 sm vis, 500 ft below / 1,000 ft above / 2,000 ft horizontal from clouds.",
    },
    "D": {
        "label": "Class D  (Delta)",
        "color": _TEAL,
        "contact": "~5-7 nm out — Tower",
        "rule":    "Two-way radio CONTACT with tower before entering. Tower must be operational. "
                   "If tower closed, treat as Class E/G.",
        "mins":    "3 sm vis, 500 ft below / 1,000 ft above / 2,000 ft horizontal from clouds.",
    },
    "E": {
        "label": "Class E  (Echo)",
        "color": _SLATE,
        "contact": "No contact required",
        "rule":    "No radio contact required. Follow VFR cloud clearance minimums.",
        "mins":    "Below 10,000 ft MSL: 3 sm vis, 500 ft below / 1,000 ft above / 2,000 ft horizontal from clouds.",
    },
    "G": {
        "label": "Class G  (Uncontrolled)",
        "color": colors.HexColor("#6b7280"),
        "contact": "No contact required",
        "rule":    "No radio required. Monitor CTAF if near uncontrolled airport.",
        "mins":    "Day, below 1,200 ft AGL: 1 sm vis, clear of clouds.\n"
                   "Day, above 1,200 ft AGL: 1 sm vis, 500 below / 1,000 above / 2,000 horizontal from clouds.",
    },
}

# ── Styles ────────────────────────────────────────────────────────────────────
_S = getSampleStyleSheet()

def _style(name, **kw):
    base = kw.pop("parent", _S["Normal"])
    return ParagraphStyle(name, parent=base, **kw)

_TITLE  = _style("T",  fontSize=13, fontName="Helvetica-Bold",
                 textColor=_WHITE,  alignment=TA_CENTER)
_SUB    = _style("SB", fontSize=9,  fontName="Helvetica",
                 textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)
_SEC    = _style("SC", fontSize=9,  fontName="Helvetica-Bold",
                 textColor=_WHITE,  alignment=TA_LEFT)
_KEY    = _style("K",  fontSize=7,  fontName="Helvetica-Bold",
                 textColor=_SLATE)
_VAL    = _style("V",  fontSize=8,  fontName="Helvetica",
                 textColor=_NAVY,   leading=10)
_RULE   = _style("R",  fontSize=7,  fontName="Helvetica",
                 textColor=_NAVY,   leading=9)
_WARN   = _style("W",  fontSize=7,  fontName="Helvetica-Bold",
                 textColor=_RED)
_EMG    = _style("E",  fontSize=7,  fontName="Helvetica-Bold",
                 textColor=_WHITE,  alignment=TA_CENTER)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _banner(text, bg=_NAVY, style=None):
    s = style or _SEC
    tbl = Table([[Paragraph(text, s)]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), bg),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ]))
    return tbl


def _kv(rows, key_w=1.1*inch, val_w=None, total_w=None):
    """Simple key/value table."""
    if val_w is None:
        val_w = (total_w or 3.5*inch) - key_w
    data = [[Paragraph(k, _KEY), Paragraph(v, _VAL)] for k, v in rows]
    tbl = Table(data, colWidths=[key_w, val_w])
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("BACKGROUND",    (0,0), (0,-1), _LIGHT),
        ("LINEBELOW",     (0,0), (-1,-2), 0.25, _BORDER),
    ]))
    return tbl


def _bearing(lat1, lon1, lat2, lon2):
    """True bearing in degrees from point 1 to point 2."""
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _distance_nm(lat1, lon1, lat2, lon2):
    """Haversine distance in nm."""
    R    = 3440.1
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)
    a    = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))


def _route_map_png(o_lat, o_lon, d_lat, d_lon, origin, dest,
                   airspaces=None, cruise_alt_ft=3500,
                   width_in=7.0, height_in=2.4):
    """Route map via map_utils (contextily tiles or plain fallback). Print-friendly (light)."""
    try:
        from rho.modules.map_utils import generate_route_map_png
        return generate_route_map_png(
            o_lat, o_lon, d_lat, d_lon,
            origin, dest,
            airspaces=airspaces,
            cruise_alt_ft=cruise_alt_ft,
            width_in=width_in, height_in=height_in,
            dark=False,
        )
    except Exception:
        return None


# ── Airport section (departure or arrival) ────────────────────────────────────

def _airport_section(icao, assess, comms, role="DEPARTURE", col_w=3.5*inch):
    """Returns a list of flowables for one airport column."""
    role_bg = _BLUE if role == "DEPARTURE" else _GREEN
    rows    = []

    # Frequencies
    if comms.get("atis"):   rows.append(("ATIS",    comms["atis"]))
    if comms.get("clearance"): rows.append(("Clnc Del", comms["clearance"]))
    if comms.get("ground"): rows.append(("Ground",  comms["ground"]))
    if comms.get("tower"):  rows.append(("Tower",   comms["tower"]))
    if comms.get("unicom"): rows.append(("UNICOM",  comms["unicom"]))
    if comms.get("ctaf"):   rows.append(("CTAF",    comms["ctaf"]))
    if comms.get("approach"):
        seen = set()
        for a in comms["approach"]:
            freq = (a.get("freq") or "").strip()
            try:
                freq_f = float(freq.split()[0].replace(";",""))
            except (ValueError, IndexError):
                continue
            clean = freq.split()[0]
            if clean not in seen and freq_f < 136:
                lbl = "Approach" if role == "DEPARTURE" else "Approach"
                rows.append((lbl, clean))
                seen.add(clean)
                break

    # Runway
    rwy = assess.get("best_runway")
    if rwy:
        xw  = assess.get("crosswind_kt")
        xws = f" ({xw:.0f} kt XW)" if xw else ""
        rows.append(("Active Rwy", f"{rwy}{xws}"))

    # Winds
    wd = assess.get("wind_dir"); wk = assess.get("wind_kt")
    if wd is not None and wk is not None:
        rows.append(("Winds", f"{wd:03d}° @ {wk} kt"))

    # Altimeter
    alt = assess.get("altimeter")
    if alt:
        try:
            rows.append(("Altimeter", f'{float(alt):.2f}" Hg  ← SET THIS'))
        except (ValueError, TypeError):
            pass

    key_w = 0.85 * inch
    val_w = col_w - key_w - 0.1*inch

    return [
        _banner(f"  {role}  —  {icao}", bg=role_bg),
        Spacer(1, 2),
        _kv(rows, key_w=key_w, val_w=val_w),
        Spacer(1, 4),
    ]



# ── Radio scripts section ─────────────────────────────────────────────────────

def _radio_scripts_section(origin, dest, comms_o, comms_d,
                            o_ass, d_ass, tail=None, flight_rules="VFR"):
    """
    Returns a list of flowables with departure + arrival radio call scripts.
    Towered airports: ATIS → Ground → Tower → (Approach).
    Non-towered airports: AWOS/UNICOM → CTAF position calls.
    """
    call = tail if tail else "N_____"

    # Try to infer aircraft type label from display name
    # (not available here — use generic "student aircraft")
    ac_type = "student aircraft"

    o_towered = bool(comms_o.get("tower"))
    d_towered = bool(comms_d.get("tower"))

    def _freq(d, key):
        val = d.get(key)
        if not val:
            return "—"
        if isinstance(val, list):
            return val[0].get("freq", "—") if val else "—"
        return str(val)

    o_atis   = _freq(comms_o, "atis")
    o_ground = _freq(comms_o, "ground")
    o_tower  = _freq(comms_o, "tower")
    o_ctaf   = _freq(comms_o, "ctaf") or _freq(comms_o, "unicom")
    o_dep    = _freq(comms_o, "approach")   # approach doubles as departure

    d_atis   = _freq(comms_d, "atis")
    d_appr   = _freq(comms_d, "approach")
    d_tower  = _freq(comms_d, "tower")
    d_ground = _freq(comms_d, "ground")
    d_ctaf   = _freq(comms_d, "ctaf") or _freq(comms_d, "unicom")

    o_rwy = o_ass.get("best_runway") or "XX"
    d_rwy = d_ass.get("best_runway") or "XX"

    story = []
    story.append(_banner("  RADIO SCRIPTS", bg=_TEAL))
    story.append(Spacer(1, 4))

    # ── Departure scripts ─────────────────────────────────────────────────────
    story.append(Paragraph(f"<b>Departure — {origin} "
                           f"({'Towered' if o_towered else 'Non-Towered'})</b>", _KEY))
    story.append(Spacer(1, 3))

    if o_towered:
        dep_rows = []
        if o_atis != "—":
            dep_rows.append(("1  ATIS", f"[{o_atis}]  Listen for Information ___. Note altimeter."))
        if o_ground != "—":
            dep_rows.append(("2  Ground", f"[{o_ground}]  \"{origin} Ground, {call}, "
                            f"{ac_type}, at ramp, VFR to {dest} with Information ___, "
                            f"request taxi.\""))
        if o_tower != "—":
            dep_rows.append(("3  Tower", f"[{o_tower}]  \"{origin} Tower, {call}, "
                            f"holding short of runway {o_rwy}, ready for departure, "
                            f"VFR to {dest}.\""))
        if o_dep != "—":
            dep_rows.append(("4  Departure", f"[{o_dep}]  \"{origin} Departure, {call}, "
                            f"climbing through ___ft, VFR to {dest}, "
                            f"request flight following.\""))
        if dep_rows:
            story.append(_kv(dep_rows, key_w=1.0*inch, val_w=6.1*inch))
    else:
        dep_rows = []
        if o_atis != "—":
            dep_rows.append(("AWOS/UNICOM", f"[{o_atis or o_ctaf}]  Check winds and wx. Note altimeter."))
        if o_ctaf != "—":
            dep_rows.append(("Taxi", f"[{o_ctaf}]  \"{origin} traffic, {call}, "
                            f"{ac_type}, taxiing to runway {o_rwy}, {origin}.\""))
            dep_rows.append(("Takeoff", f"[{o_ctaf}]  \"{origin} traffic, {call}, "
                            f"departing runway {o_rwy}, remaining in pattern / "
                            f"departing {dest} direction, {origin}.\""))
            dep_rows.append(("Airborne", f"[{o_ctaf}]  \"{origin} traffic, {call}, "
                            f"departing {origin}, {dest} bound, "
                            f"climbing through ___ft, {origin}.\""))
        if dep_rows:
            story.append(_kv(dep_rows, key_w=1.0*inch, val_w=6.1*inch))

    story.append(Spacer(1, 6))

    # ── Arrival scripts ───────────────────────────────────────────────────────
    story.append(Paragraph(f"<b>Arrival — {dest} "
                           f"({'Towered' if d_towered else 'Non-Towered'})</b>", _KEY))
    story.append(Spacer(1, 3))

    if d_towered:
        arr_rows = []
        if d_atis != "—":
            arr_rows.append(("1  ATIS", f"[{d_atis}]  Get Information ___. Note altimeter "
                            f"and active runway before calling approach."))
        if d_appr != "—":
            arr_rows.append(("2  Approach", f"[{d_appr}]  \"{dest} Approach, {call}, "
                            f"{ac_type}, ___nm {dest} direction, ___ft, "
                            f"VFR, request landing {dest}.\""))
        if d_tower != "—":
            arr_rows.append(("3  Tower", f"[{d_tower}]  \"{dest} Tower, {call}, "
                            f"{ac_type}, ___ [position], inbound, with Information ___.\""))
        if d_ground != "—":
            arr_rows.append(("4  Ground", f"[{d_ground}]  \"{dest} Ground, {call}, "
                            f"clear of runway {d_rwy}, request taxi to ramp.\""))
        if arr_rows:
            story.append(_kv(arr_rows, key_w=1.0*inch, val_w=6.1*inch))
    else:
        arr_rows = []
        if d_ctaf != "—":
            arr_rows.append(("10 nm out", f"[{d_ctaf}]  \"{dest} traffic, {call}, "
                            f"{ac_type}, 10 miles ___ [direction], inbound, {dest}.\""))
            arr_rows.append(("45° entry", f"[{d_ctaf}]  \"{dest} traffic, {call}, "
                            f"entering 45 downwind runway {d_rwy}, {dest}.\""))
            arr_rows.append(("Downwind", f"[{d_ctaf}]  \"{dest} traffic, {call}, "
                            f"downwind runway {d_rwy}, {dest}.\""))
            arr_rows.append(("Base", f"[{d_ctaf}]  \"{dest} traffic, {call}, "
                            f"base runway {d_rwy}, {dest}.\""))
            arr_rows.append(("Final", f"[{d_ctaf}]  \"{dest} traffic, {call}, "
                            f"final runway {d_rwy}, {dest}.\""))
            arr_rows.append(("Clear", f"[{d_ctaf}]  \"{dest} traffic, {call}, "
                            f"clear of runway {d_rwy}, {dest}.\""))
        if arr_rows:
            story.append(_kv(arr_rows, key_w=1.0*inch, val_w=6.1*inch))

    story.append(Spacer(1, 4))
    return story


# ── Main generator ────────────────────────────────────────────────────────────

def generate_cheatsheet(brief, comms_o, comms_d, aircraft=None,
                        tail_number=None, flight_rules="VFR"):
    """
    Generate an in-flight cheat sheet PDF.

    Parameters
    ----------
    brief        : dict from insights.get_preflight_brief()
    comms_o      : dict from comms.get_comms(origin)
    comms_d      : dict from comms.get_comms(dest)
    aircraft     : dict from aircraft.get_aircraft() or None — adds V-speeds strip
    tail_number  : str or None — e.g. "N12345", used in radio scripts
    flight_rules : "VFR" | "IFR" — reserved for future IFR radio script variants

    Returns
    -------
    bytes — PDF ready for st.download_button
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.45*inch, rightMargin=0.45*inch,
        topMargin=0.4*inch,   bottomMargin=0.4*inch,
    )

    W = letter[0] - 0.9*inch   # usable width (~7.1 in)

    origin     = brief.get("origin_icao", "???")
    dest       = brief.get("dest_icao",   "???")
    rec        = brief.get("recommendation", "?")
    reason     = brief.get("reason", "")
    o_ass      = brief.get("origin_assess")  or {}
    d_ass      = brief.get("dest_assess")    or {}
    route      = brief.get("route")          or {}
    hazards    = brief.get("hazards")        or []
    o_apt      = brief.get("origin_apt")     or {}
    d_apt      = brief.get("dest_apt")       or {}
    cruise_alt = brief.get("cruise_alt_ft",  3500)

    direct  = (route.get("direct") or {})
    pens    = direct.get("airspace_penetrations") or []
    dist_nm = direct.get("distance_nm") or 0

    o_lat = o_apt.get("lat"); o_lon = o_apt.get("lon")
    d_lat = d_apt.get("lat"); d_lon = d_apt.get("lon")
    hdg_true = 0
    if all(v is not None for v in [o_lat, o_lon, d_lat, d_lon]):
        hdg_true = _bearing(o_lat, o_lon, d_lat, d_lon)
        if not dist_nm:
            dist_nm = _distance_nm(o_lat, o_lon, d_lat, d_lon)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    rec_clr = {"GO": _GREEN, "CAUTION": _AMBER, "NO-GO": _RED}.get(rec, _SLATE)
    ete_min = round(dist_nm / 100 * 60) if dist_nm else "?"

    hdr_data = [[
        Paragraph(f"IN-FLIGHT GUIDE", _TITLE),
        Paragraph(f"{origin}  →  {dest}", _TITLE),
        Paragraph(f"{_date.today()}", _TITLE),
    ]]
    hdr_tbl = Table(hdr_data, colWidths=[W*0.3, W*0.4, W*0.3])
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), _NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
    ]))
    story.append(hdr_tbl)

    sub_data = [[
        Paragraph(f"{dist_nm} nm  |  ETE ~{ete_min} min @ 100 kt  |  Cruise {cruise_alt} ft", _SUB),
        Paragraph(
            f'<font color="{"#15803d" if rec=="GO" else "#b45309" if rec=="CAUTION" else "#991b1b"}">'
            f'<b>{rec}</b></font>  —  {reason}', _SUB
        ),
    ]]
    sub_tbl = Table(sub_data, colWidths=[W*0.55, W*0.45])
    sub_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#0f172a")),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
    ]))
    story.append(sub_tbl)
    story.append(Spacer(1, 5))

    # ── Route map ─────────────────────────────────────────────────────────────
    if all(v is not None for v in [o_lat, o_lon, d_lat, d_lon]):
        map_png = _route_map_png(
            o_lat, o_lon, d_lat, d_lon, origin, dest,
            airspaces=brief.get("airspaces"),
            cruise_alt_ft=brief.get("cruise_alt_ft", 3500),
            width_in=W/inch, height_in=2.3,
        )
        if map_png:
            from reportlab.platypus import Image as RLImage
            story.append(RLImage(io.BytesIO(map_png), width=W, height=2.3*inch))
            story.append(Spacer(1, 5))

    # ── Row 1: Departure (left) | Arrival (right) ────────────────────────────
    half_w = (W - 0.1*inch) / 2

    dep_els = _airport_section(origin, o_ass, comms_o, "DEPARTURE", half_w)
    arr_els = _airport_section(dest,   d_ass, comms_d, "ARRIVAL",   half_w)

    def _els_to_table(els, w):
        rows = [[e] for e in els]
        t = Table(rows, colWidths=[w])
        t.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 0),
            ("BOTTOMPADDING", (0,0),(-1,-1), 0),
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ]))
        return t

    airports_row = Table(
        [[_els_to_table(dep_els, half_w), _els_to_table(arr_els, half_w)]],
        colWidths=[half_w, half_w],
    )
    airports_row.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("LINEAFTER",    (0,0),(0,-1),  0.5, _BORDER),
    ]))
    story.append(airports_row)
    story.append(Spacer(1, 6))

    # ── Row 2: En Route (full width, flows across pages if needed) ────────────
    ete_min = round(dist_nm / 100 * 60) if dist_nm else "?"

    story.append(_banner("  EN ROUTE", bg=_NAVY))
    story.append(Spacer(1, 3))

    # Heading / time / squawk summary row
    hdg_data = [
        [
            Paragraph("Heading", _KEY),
            Paragraph(f"{hdg_true:.0f}° True  (verify mag variation on sectional)", _VAL),
            Paragraph("Distance", _KEY),
            Paragraph(f"{dist_nm} nm", _VAL),
            Paragraph("ETE", _KEY),
            Paragraph(f"~{ete_min} min @ 100 kt", _VAL),
            Paragraph("Squawk", _KEY),
            Paragraph("1200 (unless assigned)", _VAL),
        ]
    ]
    hdg_tbl = Table(hdg_data,
                    colWidths=[0.75*inch, 1.65*inch, 0.65*inch, 0.65*inch,
                               0.45*inch, 1.1*inch,  0.65*inch, 1.5*inch])
    hdg_tbl.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("BACKGROUND",    (0,0),(0,0),   _LIGHT),
        ("BACKGROUND",    (2,0),(2,0),   _LIGHT),
        ("BACKGROUND",    (4,0),(4,0),   _LIGHT),
        ("BACKGROUND",    (6,0),(6,0),   _LIGHT),
        ("LINEAFTER",     (1,0),(1,0),   0.5, _BORDER),
        ("LINEAFTER",     (3,0),(3,0),   0.5, _BORDER),
        ("LINEAFTER",     (5,0),(5,0),   0.5, _BORDER),
    ]))
    story.append(hdg_tbl)
    story.append(Spacer(1, 6))

    # Airspace in crossing order — full width, no column wrapping
    if pens:
        story.append(Paragraph("<b>AIRSPACE — in crossing order along the route</b>", _KEY))
        story.append(Spacer(1, 3))

        key_w = 0.85*inch
        val_w = W - key_w - 0.05*inch

        for p in pens:
            cls  = str(p.get("class", "?")).upper()
            info = _AIRSPACE.get(cls, {})
            bg   = info.get("color", _SLATE)
            name = p.get("name", "")
            lo   = p.get("lower", "?")
            hi   = p.get("upper", "?")

            story.append(KeepTogether([
                _banner(f"  {info.get('label', f'Class {cls}')}  —  {name}", bg=bg),
                _kv([
                    ("Floor / Ceil", f"{lo}  –  {hi}"),
                    ("When to call", info.get("contact", "—")),
                    ("Rule",         info.get("rule", "—")),
                    ("VFR mins",     info.get("mins", "—")),
                ], key_w=key_w, val_w=val_w),
                Spacer(1, 5),
            ]))
    else:
        story.append(Paragraph(
            "No controlled airspace on direct route. "
            "Class E/G rules apply: 3 sm vis, 500 ft below / 1,000 ft above / 2,000 ft horizontal from clouds.",
            _RULE,
        ))
        story.append(Spacer(1, 6))

    # Weather concerns
    if hazards:
        story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
        story.append(Spacer(1, 3))
        story.append(Paragraph("<b>WEATHER CONCERNS</b>", _WARN))
        story.append(Spacer(1, 2))
        for h in hazards[:5]:
            story.append(Paragraph(f"  -  {h}", _RULE))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 4))

    # ── Radio scripts ─────────────────────────────────────────────────────────
    story += _radio_scripts_section(
        origin, dest, comms_o, comms_d,
        o_ass, d_ass,
        tail=tail_number,
        flight_rules=flight_rules,
    )

    # ── V-speeds strip (if aircraft provided) ─────────────────────────────────
    if aircraft:
        vs_text = (
            f"Vg {aircraft['vg']} kt  |  Vx {aircraft['vx']} kt  |  "
            f"Vy {aircraft['vy']} kt  |  Vs0 {aircraft['vs0']} kt  |  "
            f"Vs1 {aircraft['vs1']} kt  |  Va {aircraft['va']} kt  |  "
            f"Vno {aircraft['vno']} kt  |  Vne {aircraft['vne']} kt"
        )
        vs_data = [[
            Paragraph(aircraft["display"], _KEY),
            Paragraph(vs_text, _VAL),
        ]]
        vs_tbl = Table(vs_data, colWidths=[W * 0.25, W * 0.75])
        vs_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(0,0),   _LIGHT),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING",   (0,0),(-1,-1), 4),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ]))
        story.append(vs_tbl)
        story.append(Spacer(1, 4))

    # ── Emergency strip ───────────────────────────────────────────────────────
    emg_data = [[
        Paragraph("GUARD  121.5 MHz", _EMG),
        Paragraph("EMERGENCY  7700", _EMG),
        Paragraph("RADIO FAIL  7600", _EMG),
        Paragraph("HIJACK  7500", _EMG),
        Paragraph("BEST GLIDE → MAYDAY → FIELD → ABCDE", _EMG),
    ]]
    emg_tbl = Table(emg_data, colWidths=[W*0.18, W*0.15, W*0.15, W*0.12, W*0.4])
    emg_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), _RED),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("LINEAFTER",     (0,0),(-2,-1), 0.5, colors.HexColor("#fca5a5")),
    ]))
    story.append(emg_tbl)

    doc.build(story)
    return buf.getvalue()
