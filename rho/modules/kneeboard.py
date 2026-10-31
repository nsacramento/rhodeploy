"""
Rho — VFR Kneeboard (single in-flight document)

Replaces the former separate "In-Flight Guide" (cheatsheet.py) and
"Pre-Flight Kneeboard". Organised the way the flight unfolds:

  PAGE 1 — FLIGHT CARD
    Header (route, aircraft, brief time, GO/CAUTION/NO-GO)
    Route strip (distance, TC/MC, altitude + 91.159 check, TAS/GS, ETE, fuel, squawk)
    Route map
    DEPARTURE | ARRIVAL panels: frequencies in call order, weather, active runway
        with headwind/crosswind, raw METAR + TAF, ATIS copy line
    EN ROUTE: airspace in crossing order (who to call, on what frequency),
        winds aloft at cruise, hazards, flight-following write-in

  PAGE 2 — AIRPORTS & RADIO
    Runway diagrams (origin + destination) with active runway and wind
    Radio scripts (towered / non-towered, correct facility names)
    Aircraft V-speeds, emergency + lost-comms, light-gun signals (if towered)
    Times / notes

  Emergency strip printed at the bottom of every page.

Usage:
    from rho.modules.kneeboard import generate_kneeboard
    pdf_bytes = generate_kneeboard(brief, comms_o, comms_d,
                                   aircraft=ac, tail_number="N12345")
"""

import io
import math
from datetime import date as _date, datetime as _dt

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, Image, PageBreak, CondPageBreak,
)

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY   = colors.HexColor("#0f172a")
_INK    = colors.HexColor("#1e293b")
_BLUE   = colors.HexColor("#1e40af")
_GREEN  = colors.HexColor("#15803d")
_AMBER  = colors.HexColor("#b45309")
_RED    = colors.HexColor("#b91c1c")
_PURPLE = colors.HexColor("#6d28d9")
_TEAL   = colors.HexColor("#0e7490")
_SLATE  = colors.HexColor("#475569")
_MUTED  = colors.HexColor("#64748b")
_LIGHT  = colors.HexColor("#f1f5f9")
_BORDER = colors.HexColor("#cbd5e1")
_WHITE  = colors.white

_CAT_CLR = {"VFR": _GREEN, "MVFR": _BLUE, "IFR": _RED, "LIFR": colors.HexColor("#a21caf")}
_REC_CLR = {"GO": _GREEN, "CAUTION": _AMBER, "NO-GO": _RED}
_CLS_CLR = {"B": _BLUE, "C": _PURPLE, "D": _TEAL, "E": _SLATE}

# ── Styles ────────────────────────────────────────────────────────────────────
_S = getSampleStyleSheet()


def _st(name, **kw):
    return ParagraphStyle(name, parent=_S["Normal"], **kw)


_TITLE  = _st("kT", fontName="Helvetica-Bold", fontSize=13, textColor=_WHITE, leading=15)
_TITLER = _st("kTR", fontName="Helvetica-Bold", fontSize=13, textColor=_WHITE,
              leading=15, alignment=TA_RIGHT)
_HSUB   = _st("kHS", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#cbd5e1"), leading=10)
_HSUBR  = _st("kHSR", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#cbd5e1"),
              leading=10, alignment=TA_RIGHT)
_BAN    = _st("kB", fontName="Helvetica-Bold", fontSize=9, textColor=_WHITE, leading=11)
_BANR   = _st("kBR", fontName="Helvetica", fontSize=7.5, textColor=_WHITE, leading=9, alignment=TA_RIGHT)
_SUBH   = _st("kSH", fontName="Helvetica-Bold", fontSize=7, textColor=_MUTED, leading=9,
              spaceBefore=2)
_KEY    = _st("kK", fontName="Helvetica-Bold", fontSize=6.8, textColor=_MUTED, leading=9)
_VAL    = _st("kV", fontName="Helvetica", fontSize=8, textColor=_INK, leading=10)
_VALB   = _st("kVB", fontName="Helvetica-Bold", fontSize=8.5, textColor=_INK, leading=10.5)
_FREQ   = _st("kF", fontName="Helvetica-Bold", fontSize=10, textColor=_INK, leading=12)
_SMALL  = _st("kS", fontName="Helvetica", fontSize=6.8, textColor=_MUTED, leading=8.5)
_MONO   = _st("kM", fontName="Courier", fontSize=6.6, textColor=_INK, leading=8)
_STRK   = _st("kSK", fontName="Helvetica-Bold", fontSize=6, textColor=_MUTED, leading=7.5,
              alignment=TA_CENTER)
_STRV   = _st("kSV", fontName="Helvetica-Bold", fontSize=9.5, textColor=_INK, leading=11,
              alignment=TA_CENTER)
_STRN   = _st("kSN", fontName="Helvetica", fontSize=6, textColor=_MUTED, leading=7.5,
              alignment=TA_CENTER)
_SCRIPT = _st("kSC", fontName="Helvetica", fontSize=7.6, textColor=_INK, leading=9.6)

_PAGE_W, _PAGE_H = letter
_MARGIN = 0.4 * inch
_W = _PAGE_W - 2 * _MARGIN


# ── Small helpers ─────────────────────────────────────────────────────────────

def _hex(c):
    return "#" + c.hexval()[2:]


def _banner(left, bg=_INK, right=None, w=None):
    w = w or _W
    if right:
        data = [[Paragraph(left, _BAN), Paragraph(right, _BANR)]]
        tbl = Table(data, colWidths=[w * 0.38, w * 0.62])
    else:
        tbl = Table([[Paragraph(left, _BAN)]], colWidths=[w])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


def _kv(rows, key_w, val_w, val_style=_VAL, zebra=False):
    data = []
    for k, v in rows:
        vv = v if hasattr(v, "wrap") else Paragraph(str(v), val_style)
        data.append([Paragraph(k, _KEY), vv])
    if not data:
        return Spacer(1, 1)
    tbl = Table(data, colWidths=[key_w, val_w])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, _BORDER),
    ]
    if zebra:
        style.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [_WHITE, _LIGHT]))
    tbl.setStyle(TableStyle(style))
    return tbl


def _stack(flowables, w):
    """Put a list of flowables into a single-column table (for side-by-side layout)."""
    t = Table([[f] for f in flowables], colWidths=[w])
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _side_by_side(left, right, gap=0.14 * inch):
    half = (_W - gap) / 2
    t = Table([[_stack(left, half), "", _stack(right, half)]],
              colWidths=[half, gap, half])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _bearing(lat1, lon1, lat2, lon2):
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dlo = math.radians(lon2 - lon1)
    x = math.sin(dlo) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _distance_nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3440.065 * 2 * math.asin(math.sqrt(a))


def _mag_var_west(lat, lon):
    """Rough magnetic variation, degrees WEST positive (same model as navlog.py)."""
    return round((lon + 80) * -0.4 + 5, 1)


def _wind_triangle(tas, wd, ws, tc):
    """Return (wca_deg, gs_kt). wd = direction wind is FROM (true)."""
    if not ws or not tas:
        return 0.0, float(tas or 0)
    ang = math.radians(wd - tc)
    sin_wca = max(-1.0, min(1.0, ws * math.sin(ang) / tas))
    wca = math.degrees(math.asin(sin_wca))
    gs = tas * math.cos(math.radians(wca)) - ws * math.cos(ang)
    return wca, max(gs, 1.0)


_NAME_DROP = {"INTL", "INTERNATIONAL", "MUNI", "MUNICIPAL", "RGNL", "REGIONAL", "ARPT",
              "AIRPORT", "FIELD", "FLD", "EXEC", "EXECUTIVE", "COUNTY", "CO", "AIRPARK",
              "MEMORIAL", "MEML", "AIRFIELD", "METRO", "METROPOLITAN"}


def _atc_name(apt, icao):
    """'SARASOTA/BRADENTON INTL' -> 'Sarasota'. Falls back to ICAO."""
    name = ((apt or {}).get("name") or "").upper()
    if not name:
        return icao
    first = name.replace("-", "/").split("/")[0]
    words = [w for w in first.split() if w not in _NAME_DROP]
    return " ".join(words).title() if words else icao


def _fmt_freq(f):
    return str(f) if f else "—"


def _first_approach(comms):
    for a in (comms or {}).get("approach") or []:
        try:
            if float(str(a.get("freq", "")).split()[0]) < 136:
                return a
        except (ValueError, IndexError):
            continue
    return None


def _altimeter(assess):
    try:
        return f'{float(assess.get("altimeter")):.2f}'
    except (TypeError, ValueError):
        return None


def _rwy_short(ident):
    """'04' -> '4', '14L' -> '14L' (how runways are spoken / written on scripts)."""
    if not ident:
        return "__"
    return ident.lstrip("0") or ident


# ── Airport diagrams / active runway ─────────────────────────────────────────

def _layout_and_active(icao, apt, assess):
    try:
        from rho.modules.airport_diagram import get_airport_layout, pick_active_end
        layout = get_airport_layout(icao, (apt or {}).get("runways"))
        active = pick_active_end(layout, assess.get("best_runway"),
                                 assess.get("wind_dir"), assess.get("wind_kt"))
        return layout, active
    except Exception:
        return None, None


def _diagram_png(icao, apt, assess, layout, active, w_in, h_in):
    if not layout:
        return None
    try:
        from rho.modules.airport_diagram import generate_airport_diagram_png
        elev = (apt or {}).get("elevation_ft")
        sub_parts = []
        if (apt or {}).get("name"):
            sub_parts.append(apt["name"].title())
        if elev is not None:
            sub_parts.append(f"Elev {elev:,} ft")
        return generate_airport_diagram_png(
            layout, active, assess.get("wind_dir"), assess.get("wind_kt"),
            title=icao, subtitle="  ·  ".join(sub_parts),
            width_in=w_in, height_in=h_in, dark=False, dpi=200,
        )
    except Exception:
        return None


# ── Sections ──────────────────────────────────────────────────────────────────

def _header(brief, aircraft, tail_number):
    origin, dest = brief.get("origin_icao", "???"), brief.get("dest_icao", "???")
    rec = brief.get("recommendation", "?")
    reason = brief.get("reason", "")
    ac = aircraft.get("display") if aircraft else "Aircraft not set"
    if tail_number:
        ac = f"{ac}  ·  {tail_number}"
    now = _dt.utcnow().strftime("%Y-%m-%d %H%MZ")

    top = Table([[
        Paragraph("RHO  ·  VFR KNEEBOARD", _TITLE),
        Paragraph(f"{origin}  →  {dest}", _TITLER),
    ], [
        Paragraph(ac, _HSUB),
        Paragraph(f"Brief {now}  ·  wx changes — get ATIS/AWOS", _HSUBR),
    ]], colWidths=[_W * 0.5, _W * 0.5])
    top.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    rec_tbl = _banner(f"{rec}  —  {reason}", bg=_REC_CLR.get(rec, _SLATE))
    out = [top, rec_tbl]
    why = [f for f in (brief.get("factors") or []) if f.get("level") != "NOTE"][:3]
    if why:
        lines = "<br/>".join(
            f"<b>{f.get('airport', '')} · {f.get('type', '')}:</b> {f.get('detail', '')}" for f in why)
        t = Table([[Paragraph(lines, _VAL)]], colWidths=[_W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7") if rec == "CAUTION"
             else colors.HexColor("#fee2e2")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        out.append(t)
    return out


def _route_strip(brief, aircraft, comms_o):
    o_apt = brief.get("origin_apt") or {}
    d_apt = brief.get("dest_apt") or {}
    route = (brief.get("route") or {}).get("direct") or {}
    cruise = brief.get("cruise_alt_ft") or 3500

    o_lat, o_lon = o_apt.get("lat"), o_apt.get("lon")
    d_lat, d_lon = d_apt.get("lat"), d_apt.get("lon")
    have = all(v is not None for v in (o_lat, o_lon, d_lat, d_lon))

    dist = route.get("distance_nm")
    tc = None
    if have:
        tc = _bearing(o_lat, o_lon, d_lat, d_lon)
        if not dist:
            dist = round(_distance_nm(o_lat, o_lon, d_lat, d_lon), 1)
    var_w = _mag_var_west(o_lat, o_lon) if have else 0
    mc = (tc + var_w) % 360 if tc is not None else None

    # Winds aloft nearest cruise
    wa = brief.get("winds_aloft") or {}
    wa_pick = None
    if wa:
        try:
            k = min(wa.keys(), key=lambda a: abs(int(a) - cruise))
            wa_pick = (int(k), wa[k])
        except (ValueError, TypeError):
            wa_pick = None

    tas = (aircraft or {}).get("cruise_ktas") or 100
    gs, wca = float(tas), 0.0
    if wa_pick and tc is not None and wa_pick[1].get("dir") is not None:
        wca, gs = _wind_triangle(tas, wa_pick[1]["dir"], wa_pick[1].get("spd") or 0, tc)
    mh = (mc + wca) % 360 if mc is not None else None
    ete = round(dist / gs * 60) if dist and gs else None

    burn = (aircraft or {}).get("fuel_burn_gph")
    fuel_txt, fuel_note = "—", "set aircraft"
    if burn and ete is not None:
        trip = burn * (ete / 60 + 0.2)          # +12 min taxi/climb allowance
        fuel_txt = f"{trip:.1f} gal"
        fuel_note = f"+{burn * 0.5:.1f} gal 30-min reserve"

    # 14 CFR 91.159 hemispheric rule (applies > 3,000 ft AGL)
    elev = max(o_apt.get("elevation_ft") or 0, d_apt.get("elevation_ft") or 0)
    alt_note = "91.159 n/a ≤3,000 AGL"
    if mc is not None and cruise - elev > 3000:
        want_odd = mc < 180
        thousands = int(cruise // 1000)
        ok = (cruise % 1000 == 500) and ((thousands % 2 == 1) == want_odd)
        rule = "odd+500" if want_odd else "even+500"
        alt_note = f"OK {rule} (91.159)" if ok else f"<font color='#b91c1c'><b>USE {rule.upper()} (91.159)</b></font>"

    sq_note = "until assigned"
    if (comms_o or {}).get("has_tower"):
        sq_note = "or as assigned by clnc"

    cells = [
        ("DIST", f"{dist:.1f} nm" if isinstance(dist, (int, float)) else "—", "direct"),
        ("COURSE", f"{tc:03.0f}°T / {mc:03.0f}°M" if tc is not None else "—",
         f"var ~{abs(var_w):.0f}°{'W' if var_w >= 0 else 'E'} — verify"),
        ("HEADING", f"{mh:03.0f}°M" if mh is not None else "—",
         f"WCA {wca:+.0f}°" if wa_pick else "no winds aloft"),
        ("ALTITUDE", f"{cruise:,} MSL", alt_note),
        ("TAS / GS", f"{tas:.0f} / {gs:.0f} kt",
         f"wind {wa_pick[1].get('dir', 0):03d}@{wa_pick[1].get('spd', 0)} @ {wa_pick[0]//1000}k"
         if wa_pick else "GS = TAS (no wind)"),
        ("ETE", f"{ete} min" if ete is not None else "—", "cruise GS"),
        ("FUEL", fuel_txt, fuel_note),
        ("SQUAWK", "1200", sq_note),
    ]
    row_k = [Paragraph(c[0], _STRK) for c in cells]
    row_v = [Paragraph(c[1], _STRV) for c in cells]
    row_n = [Paragraph(c[2], _STRN) for c in cells]
    widths = [0.8, 1.15, 0.9, 1.1, 1.05, 0.65, 0.95, 1.1]
    scale = _W / (sum(widths) * inch)
    t = Table([row_k, row_v, row_n], colWidths=[w * inch * scale for w in widths])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, _BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t, {"tc": tc, "mc": mc, "dist": dist, "ete": ete, "gs": gs, "wa": wa_pick}


def _freq_rows(comms, role, atc):
    """Frequencies in the order the pilot will use them."""
    c = comms or {}
    towered = bool(c.get("has_tower"))
    wx_lbl = c.get("wx_label") or "ATIS"
    appr = _first_approach(c)
    appr_name = (appr or {}).get("facility") or "Approach"
    rows = []
    if c.get("atis"):
        rows.append((wx_lbl, c["atis"]))
    if role == "DEPARTURE":
        if towered:
            if c.get("clearance"):
                rows.append(("Clearance", c["clearance"]))
            if c.get("ground"):
                rows.append(("Ground", c["ground"]))
            if c.get("tower"):
                rows.append((f"{atc} Tower", c["tower"]))
            if appr:
                rows.append((f"{appr_name} Departure", appr["freq"]))
        else:
            if c.get("ctaf"):
                rows.append(("CTAF", c["ctaf"]))
            if c.get("unicom") and c.get("unicom") != c.get("ctaf"):
                rows.append(("UNICOM", c["unicom"]))
            if appr:
                rows.append((f"{appr_name} App (FF)", appr["freq"]))
    else:
        if towered:
            if appr:
                rows.append((f"{appr_name} Approach", appr["freq"]))
            if c.get("tower"):
                rows.append((f"{atc} Tower", c["tower"]))
            if c.get("ground"):
                rows.append(("Ground", c["ground"]))
        else:
            if appr:
                rows.append((f"{appr_name} App (FF)", appr["freq"]))
            if c.get("ctaf"):
                rows.append(("CTAF", c["ctaf"]))
            if c.get("unicom") and c.get("unicom") != c.get("ctaf"):
                rows.append(("UNICOM", c["unicom"]))
    if not rows:
        rows.append(("Freqs", "not found — check Chart Supplement"))
    return rows


def _airport_panel(role, icao, apt, assess, wx, comms, active, w):
    towered = bool((comms or {}).get("has_tower"))
    atc = _atc_name(apt, icao)
    cat = assess.get("category", "?")
    bg = _BLUE if role == "DEPARTURE" else _GREEN
    elev = (apt or {}).get("elevation_ft")
    tpa = f"TPA ~{elev + 1000:,}" if elev is not None else ""
    right = f"{'Towered' if towered else 'Non-towered'}  ·  Elev {elev if elev is not None else '?'}  ·  {tpa}"
    els = [_banner(f"{role}  ·  {icao}", bg=bg, right=right, w=w), Spacer(1, 2)]

    # Frequencies — big and in order
    key_w = w * 0.46
    fr = _freq_rows(comms, role, atc)
    els.append(_kv([(k, Paragraph(_fmt_freq(v), _FREQ)) for k, v in fr], key_w, w - key_w, zebra=True))
    els.append(Spacer(1, 3))

    # Weather
    rows = []
    cat_c = _hex(_CAT_CLR.get(cat, _SLATE))
    wd, wk = assess.get("wind_dir"), assess.get("wind_kt")
    wind = "Calm" if not wk else (f"{wd:03d}° @ {wk} kt" if wd is not None else f"VRB @ {wk} kt")
    rows.append(("Category / Wind", f"<font color='{cat_c}'><b>{cat}</b></font>   ·   {wind}"))
    vis = assess.get("visibility")
    sky = assess.get("sky_conditions") or "CLR"
    ceil = assess.get("ceiling_ft")
    rows.append(("Vis / Sky", f"{vis if vis is not None else '?'} sm   ·   {sky}"
                 + (f"   (ceiling {ceil:,})" if ceil else "")))
    tc, dc = assess.get("temp_c"), assess.get("dewpoint_c")
    if tc is not None:
        td = f"  ·  Dew {dc}°C  (spread {round(tc - dc, 1)}°)" if dc is not None else ""
        rows.append(("Temp", f"{tc}°C{td}"))
    alt = _altimeter(assess)
    if alt:
        rows.append(("Altimeter", Paragraph(f'<b>{alt}" Hg</b>  — set it', _VALB)))
    if active:
        dims = ""
        if active.get("length_ft"):
            dims = f"  ({active['length_ft']:,} x {active.get('width_ft') or '?'})"
        hw = active.get("headwind") or 0
        comp = "calm" if not wk else (
            (f"HW {hw:.0f}" if hw >= 0 else f"<font color='#b91c1c'>TAILWIND {abs(hw):.0f}</font>")
            + f" · XW {active.get('crosswind', 0):.0f}"
            + (f" {active['side']}" if active.get("side") and active.get("crosswind", 0) >= 1 else ""))
        rows.append(("Favored rwy", Paragraph(f"<b>Rwy {_rwy_short(active['ident'])}</b>{dims}  ·  {comp}", _VAL)))
    elif assess.get("best_runway"):
        rows.append(("Favored rwy", assess["best_runway"]))
    els.append(_kv(rows, key_w * 0.62, w - key_w * 0.62))

    # Raw METAR / TAF
    raw_m = assess.get("raw_metar")
    taf = (wx or {}).get("taf") or {}
    raw_t = taf.get("raw") if isinstance(taf, dict) else None
    els.append(Spacer(1, 2))
    if raw_m:
        m = raw_m[6:] if raw_m.startswith("METAR ") else raw_m
        m = m[6:] if m.startswith("SPECI ") else m
        els.append(Paragraph(f"<b>METAR</b> {m}", _MONO))
    if raw_t:
        t = raw_t[4:] if raw_t.startswith("TAF ") else raw_t
        t = t if len(t) <= 330 else t[:327] + "..."
        els.append(Paragraph(f"<b>TAF</b> {t}", _MONO))
    else:
        els.append(Paragraph(f"<b>TAF</b> none issued for {icao} — check nearest TAF / area forecast", _MONO))

    # ATIS / AWOS copy line
    els.append(Spacer(1, 3))
    wx_lbl = (comms or {}).get("wx_label") or "ATIS"
    copy = Table([[Paragraph(f"{wx_lbl} copy", _KEY), Paragraph("Info", _SMALL), "",
                   Paragraph("Wind", _SMALL), "", Paragraph("Alt", _SMALL), "",
                   Paragraph("Rwy", _SMALL), ""]],
                 colWidths=[w * 0.17, w * 0.07, w * 0.08, w * 0.09, w * 0.17,
                            w * 0.07, w * 0.14, w * 0.08, w * 0.13])
    copy.setStyle(TableStyle([
        ("LINEBELOW", (2, 0), (2, 0), 0.6, _MUTED), ("LINEBELOW", (4, 0), (4, 0), 0.6, _MUTED),
        ("LINEBELOW", (6, 0), (6, 0), 0.6, _MUTED), ("LINEBELOW", (8, 0), (8, 0), 0.6, _MUTED),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    els.append(copy)
    return els


_AIRSPACE_RULE = {
    "B": "ATC CLEARANCE required — hear \"cleared into the Class Bravo\". 3 sm, clear of clouds.",
    "C": "Two-way radio contact before entering (ATC says your callsign). 3 sm, 500 below / 1,000 above / 2,000 horiz.",
    "D": "Two-way radio contact with tower before entering. 3 sm, 500 below / 1,000 above / 2,000 horiz.",
    "E": "No contact required. Below 10,000: 3 sm, 500 below / 1,000 above / 2,000 horiz.",
}


def _enroute(brief, comms_o, comms_d, o_apt, d_apt, nav):
    origin, dest = brief.get("origin_icao", "?"), brief.get("dest_icao", "?")
    route = (brief.get("route") or {}).get("direct") or {}
    pens = route.get("airspace_penetrations") or []
    els = [_banner("EN ROUTE", bg=_INK), Spacer(1, 2)]

    appr_o = _first_approach(comms_o)
    appr_d = _first_approach(comms_d)
    o_atc, d_atc = _atc_name(o_apt, origin), _atc_name(d_apt, dest)

    rows = []
    for p in pens:
        cls = str(p.get("class", "?")).upper()
        name = (p.get("name") or "").replace(" CLASS " + cls, "").title()
        lo, hi = p.get("lower", "?"), p.get("upper", "?")
        who = ""
        nm_up = name.upper()
        if cls in ("B", "C"):
            src = None
            if o_atc.upper() in nm_up or origin[1:] in nm_up:
                src = appr_o
            elif d_atc.upper() in nm_up or dest[1:] in nm_up:
                src = appr_d
            src = src or appr_o or appr_d
            if src:
                who = f"Call <b>{src.get('facility') or 'Approach'} {src['freq']}</b> before entering. "
        elif cls == "D":
            if o_atc.upper() in nm_up and (comms_o or {}).get("tower"):
                who = f"<b>{o_atc} Tower {comms_o['tower']}</b>. "
            elif d_atc.upper() in nm_up and (comms_d or {}).get("tower"):
                who = f"<b>{d_atc} Tower {comms_d['tower']}</b>. "
        clr = _hex(_CLS_CLR.get(cls, _SLATE))
        rows.append((
            Paragraph(f"<font color='{clr}'><b>Class {cls}</b></font>", _VAL),
            Paragraph(f"<b>{name}</b>  {lo}–{hi}<br/>{who}{_AIRSPACE_RULE.get(cls, '')}", _VAL),
        ))
    if not rows:
        rows.append((Paragraph("Airspace", _KEY),
                     Paragraph("No Class B/C/D on the direct route at cruise. Class E/G VFR minimums apply.", _VAL)))
    t = Table([[a, b] for a, b in rows], colWidths=[0.75 * inch, _W - 0.75 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, _BORDER),
    ]))
    els.append(t)

    # Hazards (airspace already shown above)
    hazards = [h for h in (brief.get("hazards") or []) if not h.startswith("Route penetrates")]
    if hazards:
        els.append(Spacer(1, 3))
        els.append(Paragraph("<font color='#b91c1c'><b>HAZARDS</b></font>  " +
                             "  ·  ".join(hazards[:6]), _VAL))

    # Flight following / write-in
    els.append(Spacer(1, 4))
    ff = Table([[Paragraph("Flight following", _KEY),
                 Paragraph("Squawk", _SMALL), "", Paragraph("Freq", _SMALL), "",
                 Paragraph("Off", _SMALL), "", Paragraph("ETA", _SMALL), "",
                 Paragraph("On", _SMALL), ""]],
               colWidths=[x * _W for x in (0.15, 0.07, 0.11, 0.06, 0.13, 0.05, 0.1, 0.05, 0.1, 0.05, 0.13)])
    ff.setStyle(TableStyle(
        [("LINEBELOW", (i, 0), (i, 0), 0.6, _MUTED) for i in (2, 4, 6, 8, 10)] + [
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
    els.append(ff)
    return els


# ── Radio scripts ─────────────────────────────────────────────────────────────

def _scripts(brief, comms_o, comms_d, o_apt, d_apt, o_act, d_act, aircraft, tail_number, nav):
    origin, dest = brief.get("origin_icao", "?"), brief.get("dest_icao", "?")
    o_atc, d_atc = _atc_name(o_apt, origin), _atc_name(d_apt, dest)
    call = tail_number or "N_____"
    ac_type = "Cessna"
    if aircraft:
        ac_type = (aircraft.get("manufacturer") or "") + " " + (aircraft.get("model") or "")
        ac_type = ac_type.strip() or aircraft.get("display", "")
    alt = brief.get("cruise_alt_ft") or 3500
    o_rwy = _rwy_short((o_act or {}).get("ident"))
    d_rwy = _rwy_short((d_act or {}).get("ident"))
    co, cd = comms_o or {}, comms_d or {}
    appr_o, appr_d = _first_approach(co), _first_approach(cd)

    def F(x):
        return f"<font color='#0e7490'><b>[{x}]</b></font>  " if x else ""

    def Q(s):
        return f"“{s}”"

    # ── Departure
    dep = []
    o_wx = co.get("wx_label") or "ATIS"
    if co.get("has_tower"):
        if co.get("atis"):
            dep.append((o_wx, F(co["atis"]) + "Copy information letter, wind, altimeter, runway."))
        if co.get("clearance"):
            dep.append(("Clearance", F(co["clearance"]) + Q(
                f"{o_atc} Clearance, {call}, {ac_type}, VFR to {dest}, {alt:,}, with information ___.")
                + "  Write down squawk + departure freq; read back."))
        if co.get("ground"):
            dep.append(("Ground", F(co["ground"]) + Q(
                f"{o_atc} Ground, {call}, at ___ ramp, VFR to {dest} with information ___, ready to taxi.")
                + "  Read back hold-short instructions."))
        if co.get("tower"):
            dep.append(("Tower", F(co["tower"]) + Q(
                f"{o_atc} Tower, {call}, holding short runway {o_rwy}, ready for departure, VFR to {dest}.")))
        if appr_o:
            dep.append(("Departure", F(appr_o["freq"]) + Q(
                f"{appr_o.get('facility') or 'Departure'} Departure, {call}, climbing through ___, for {alt:,}.")))
    else:
        if co.get("atis"):
            dep.append((o_wx, F(co["atis"]) + "Wind, altimeter, choose runway (favored: "
                        f"<b>{o_rwy}</b>)."))
        ctaf = co.get("ctaf") or co.get("unicom")
        if ctaf:
            dep.append(("Taxi", F(ctaf) + Q(f"{o_atc} traffic, {ac_type} {call}, taxiing to runway {o_rwy}, {o_atc}.")))
            dep.append(("Takeoff", F(ctaf) + Q(
                f"{o_atc} traffic, {ac_type} {call}, departing runway {o_rwy}, departing to the ___, {o_atc}.")))
        if appr_o:
            dep.append(("Flight follow.", F(appr_o["freq"]) + Q(
                f"{appr_o.get('facility') or ''} Approach, {call}, request VFR flight following.").replace("  ", " ")
                + "  Then: position, altitude, destination."))

    # ── Arrival
    arr = []
    d_wx = cd.get("wx_label") or "ATIS"
    if cd.get("has_tower"):
        if cd.get("atis"):
            arr.append((f"{d_wx} (~25 nm)", F(cd["atis"]) + "Copy before first call."))
        if appr_d:
            arr.append(("Approach", F(appr_d["freq"]) + Q(
                f"{appr_d.get('facility') or ''} Approach, {call}, ___ miles ___ of {d_atc}, {alt:,}, "
                f"landing {d_atc} with information ___.").replace("  ", " ")))
        if cd.get("tower"):
            arr.append(("Tower", F(cd["tower"]) + Q(
                f"{d_atc} Tower, {call}, ___ miles ___, {alt:,}, inbound for landing with information ___.")
                + "  Read back runway + pattern entry."))
        if cd.get("ground"):
            arr.append(("Ground", F(cd["ground"]) + Q(
                f"{d_atc} Ground, {call}, clear of runway {d_rwy} at ___, taxi to ___.")))
    else:
        if cd.get("atis"):
            arr.append((f"{d_wx} (~15 nm)", F(cd["atis"]) + "Wind + altimeter → pick runway (favored: "
                        f"<b>{d_rwy}</b>)."))
        if appr_d or appr_o:
            arr.append(("Leave FF", "If on flight following: "
                        + Q(f"{call}, {d_atc} in sight / field in sight, request frequency change.")))
        ctaf = cd.get("ctaf") or cd.get("unicom")
        if ctaf:
            arr.append(("10 nm", F(ctaf) + Q(f"{d_atc} traffic, {ac_type} {call}, 10 miles ___, inbound, "
                                             f"will enter 45 for left downwind runway {d_rwy}, {d_atc}.")))
            arr.append(("Pattern", F(ctaf) + Q(f"{d_atc} traffic, {call}, left downwind / base / final runway "
                                               f"{d_rwy}, {d_atc}.") + "  Verify L/R traffic in Chart Supplement."))
            arr.append(("Clear", F(ctaf) + Q(f"{d_atc} traffic, {call}, clear of runway {d_rwy}, {d_atc}.")))
    return dep, arr


def _scripts_table(title, rows, bg):
    els = [_banner(title, bg=bg), Spacer(1, 1)]
    if not rows:
        els.append(Paragraph("No frequencies found — check Chart Supplement.", _SMALL))
        return els
    data = [[Paragraph(k, _KEY), Paragraph(v, _SCRIPT)] for k, v in rows]
    t = Table(data, colWidths=[0.95 * inch, _W - 0.95 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_WHITE, _LIGHT]),
    ]))
    els.append(t)
    return els


# ── Aircraft + emergency ─────────────────────────────────────────────────────

def _aircraft_block(aircraft, w):
    els = [_banner("AIRCRAFT", bg=_INK, w=w), Spacer(1, 1)]
    if not aircraft:
        els.append(Paragraph("No aircraft selected — choose one in the brief to print V-speeds.", _SMALL))
        return els
    a = aircraft
    vs = [("Vr / Vx / Vy", f"{a.get('vr', '—') if a.get('vr') else '—'} / {a['vx']} / {a['vy']} kt"),
          ("Best glide Vg", f"<b>{a['vg']} kt</b>"),
          ("Vs0 / Vs1", f"{a['vs0']} / {a['vs1']} kt"),
          ("Vfe / Va", f"{a.get('vfe', '—')} / {a['va']} kt (at gross)"),
          ("Vno / Vne", f"{a['vno']} / {a['vne']} kt"),
          ("Fuel", f"{a['fuel_usable_gal']} gal usable · {a['fuel_burn_gph']} gph")]
    if not a.get("vr"):
        vs[0] = ("Vx / Vy", f"{a['vx']} / {a['vy']} kt")
    els.append(_kv(vs, w * 0.36, w * 0.64))
    els.append(Paragraph("Verify against your aircraft's POH.", _SMALL))
    return els


def _emergency_block(w, towered):
    els = [_banner("EMERGENCY / LOST COMMS", bg=_RED, w=w), Spacer(1, 1)]
    rows = [
        ("Engine failure", "<b>A</b>irspeed (Vg) · <b>B</b>est field · <b>C</b>hecklist · "
                           "<b>D</b>eclare (121.5 / 7700) · <b>E</b>xecute"),
        ("Lost comms", "Squawk <b>7600</b>. Stay VFR, land at nearest suitable. "
                       "Towered: watch for light gun."),
        ("Lost / unsure", "Climb · Communicate · Confess · Comply · Conserve. "
                          "121.5 or FF for help."),
    ]
    els.append(_kv(rows, w * 0.28, w * 0.72))
    if towered:
        els.append(Spacer(1, 2))
        lg = [["Light", "In the air", "On ground"],
              ["Steady green", "Cleared to land", "Cleared for takeoff"],
              ["Flashing green", "Return for landing", "Cleared to taxi"],
              ["Steady red", "Give way, keep circling", "STOP"],
              ["Flashing red", "Airport unsafe — don't land", "Taxi clear of runway"],
              ["Flashing white", "—", "Return to start point"],
              ["Alt. red/green", "Exercise extreme caution", "Exercise extreme caution"]]
        data = [[Paragraph(c, _KEY if i == 0 or j == 0 else _VAL) for j, c in enumerate(r)]
                for i, r in enumerate(lg)]
        t = Table(data, colWidths=[w * 0.28, w * 0.38, w * 0.34])
        t.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, _LIGHT]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, _BORDER),
        ]))
        els.append(Paragraph("LIGHT GUN SIGNALS", _SUBH))
        els.append(t)
    return els


# ── Page decoration (emergency strip + footer on every page) ─────────────────

def _on_page(canvas, doc):
    canvas.saveState()
    y = 0.42 * inch
    h = 0.24 * inch
    x = _MARGIN
    canvas.setFillColor(_RED)
    canvas.rect(x, y, _W, h, stroke=0, fill=1)
    items = ["GUARD 121.5", "EMERGENCY 7700", "LOST COMMS 7600", "HIJACK 7500",
             "ENGINE OUT: Vg → FIELD → ABCDE"]
    widths = [0.17, 0.19, 0.19, 0.15, 0.30]
    canvas.setFillColor(_WHITE)
    canvas.setFont("Helvetica-Bold", 7.5)
    cx = x
    for txt, f in zip(items, widths):
        cw = _W * f
        canvas.drawCentredString(cx + cw / 2, y + 0.085 * inch, txt)
        cx += cw
        if cx < x + _W - 1:
            canvas.setStrokeColor(colors.HexColor("#fca5a5"))
            canvas.setLineWidth(0.5)
            canvas.line(cx, y + 2, cx, y + h - 2)
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica", 6)
    canvas.drawString(x, 0.25 * inch,
                      f"Generated by Rho · {_date.today()} · Training aid only — verify with sectional, "
                      "Chart Supplement, NOTAMs, and an official briefing (1800wxbrief.com).")
    canvas.drawRightString(x + _W, 0.25 * inch, f"Page {doc.page}")
    canvas.restoreState()


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_kneeboard(brief, comms_o, comms_d, aircraft=None,
                       tail_number=None, flight_rules="VFR"):
    """
    Build the single in-flight kneeboard PDF.

    brief        : dict from insights.get_preflight_brief()
    comms_o/d    : dicts from comms.get_comms()
    aircraft     : dict from aircraft.get_aircraft() or None
    tail_number  : str or None
    flight_rules : "VFR" (reserved for IFR variant)

    Returns PDF bytes.
    """
    comms_o = comms_o or {}
    comms_d = comms_d or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=0.35 * inch, bottomMargin=0.75 * inch,
        title=f"Rho Kneeboard {brief.get('origin_icao', '')}-{brief.get('dest_icao', '')}",
        author="Rho",
    )

    origin, dest = brief.get("origin_icao", "???"), brief.get("dest_icao", "???")
    o_apt = brief.get("origin_apt") or {}
    d_apt = brief.get("dest_apt") or {}
    o_ass = brief.get("origin_assess") or {}
    d_ass = brief.get("dest_assess") or {}

    o_layout, o_act = _layout_and_active(origin, o_apt, o_ass)
    d_layout, d_act = _layout_and_active(dest, d_apt, d_ass)

    story = []

    # ── PAGE 1 ────────────────────────────────────────────────────────────────
    story += _header(brief, aircraft, tail_number)
    story.append(Spacer(1, 3))
    strip, nav = _route_strip(brief, aircraft, comms_o)
    story.append(strip)
    story.append(Spacer(1, 4))

    o_lat, o_lon = o_apt.get("lat"), o_apt.get("lon")
    d_lat, d_lon = d_apt.get("lat"), d_apt.get("lon")
    if all(v is not None for v in (o_lat, o_lon, d_lat, d_lon)):
        try:
            from rho.modules.map_utils import generate_route_map_png
            png = generate_route_map_png(
                o_lat, o_lon, d_lat, d_lon, origin, dest,
                airspaces=brief.get("airspaces"),
                cruise_alt_ft=brief.get("cruise_alt_ft", 3500),
                width_in=_W / inch, height_in=2.3, dark=False,
            )
        except Exception:
            png = None
        if png:
            story.append(Image(io.BytesIO(png), width=_W, height=2.3 * inch))
            story.append(Spacer(1, 4))

    half = (_W - 0.14 * inch) / 2
    story.append(_side_by_side(
        _airport_panel("DEPARTURE", origin, o_apt, o_ass, brief.get("origin_wx"), comms_o, o_act, half),
        _airport_panel("ARRIVAL", dest, d_apt, d_ass, brief.get("dest_wx"), comms_d, d_act, half),
    ))
    story.append(Spacer(1, 5))
    story.append(KeepTogether(_enroute(brief, comms_o, comms_d, o_apt, d_apt, nav)))

    # ── PAGE 2 ────────────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(_banner(f"AIRPORTS  ·  {origin}  →  {dest}", bg=_NAVY,
                         right="Runways to scale · taxiways not shown — use the FAA airport diagram"))
    story.append(Spacer(1, 3))
    dw, dh = half / inch, 2.85
    o_png = _diagram_png(origin, o_apt, o_ass, o_layout, o_act, dw, dh)
    d_png = _diagram_png(dest, d_apt, d_ass, d_layout, d_act, dw, dh)

    def _diag_cell(png, icao):
        if png:
            return [Image(io.BytesIO(png), width=half, height=dh * inch)]
        return [Spacer(1, 0.4 * inch),
                Paragraph(f"Runway diagram unavailable for {icao}.", _SMALL)]

    diag = _side_by_side(_diag_cell(o_png, origin), _diag_cell(d_png, dest))
    diag.setStyle(TableStyle([("BOX", (0, 0), (0, 0), 0.5, _BORDER),
                              ("BOX", (2, 0), (2, 0), 0.5, _BORDER)]))
    story.append(diag)
    story.append(Spacer(1, 5))

    dep, arr = _scripts(brief, comms_o, comms_d, o_apt, d_apt, o_act, d_act,
                        aircraft, tail_number, nav)
    o_kind = "towered" if comms_o.get("has_tower") else "non-towered"
    d_kind = "towered" if comms_d.get("has_tower") else "non-towered"
    story.append(KeepTogether(_scripts_table(f"RADIO — DEPARTURE {origin} ({o_kind})", dep, _BLUE)))
    story.append(Spacer(1, 4))
    story.append(KeepTogether(_scripts_table(f"RADIO — ARRIVAL {dest} ({d_kind})", arr, _GREEN)))
    story.append(Spacer(1, 5))

    towered = bool(comms_o.get("has_tower") or comms_d.get("has_tower"))
    story.append(CondPageBreak(2.2 * inch))
    story.append(_side_by_side(_aircraft_block(aircraft, half), _emergency_block(half, towered)))
    story.append(Spacer(1, 5))

    # Notes
    story.append(CondPageBreak(0.8 * inch))
    notes = Table([[Paragraph("NOTES  ·  Hobbs out ______  in ______    Tach out ______  in ______", _KEY)]]
                  + [[""] for _ in range(3)], colWidths=[_W])
    notes.setStyle(TableStyle([
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(notes)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
