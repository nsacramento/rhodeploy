"""
Rho — VFR Navigation Log

Generates a standard cross-country VFR nav log PDF.

Columns follow the FAA cross-country planning form:
  Checkpoint | Alt | TAS | WD/WS | WCA | MH | GS | Dist | ETE | ETA | ATA | Fuel

With only origin→dest (no intermediate waypoints), one leg is generated.
When `waypoints` is provided (list of dicts with lat/lon/name), multi-leg
legs are generated — design hook for IFR waypoints in future.

IFR note: all params accept flight_rules="VFR"/"IFR"; layout is identical.
Altitude-based IFR fields (MEA, ODP, etc.) can be added per-leg in future.
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
    KeepTogether, HRFlowable,
)

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY   = colors.HexColor("#1e293b")
_BLUE   = colors.HexColor("#1e40af")
_GREEN  = colors.HexColor("#15803d")
_AMBER  = colors.HexColor("#b45309")
_RED    = colors.HexColor("#991b1b")
_SLATE  = colors.HexColor("#475569")
_LIGHT  = colors.HexColor("#f1f5f9")
_BORDER = colors.HexColor("#cbd5e1")
_WHITE  = colors.white

_S = getSampleStyleSheet()


def _style(name, **kw):
    base = kw.pop("parent", _S["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


_TITLE  = _style("NLT",  fontSize=12, fontName="Helvetica-Bold",
                 textColor=_WHITE, alignment=TA_CENTER)
_SUB    = _style("NLSB", fontSize=8,  fontName="Helvetica",
                 textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)
_HDR    = _style("NLHD", fontSize=7,  fontName="Helvetica-Bold",
                 textColor=_WHITE, alignment=TA_CENTER)
_CELL   = _style("NLCL", fontSize=7,  fontName="Helvetica",
                 textColor=_NAVY, alignment=TA_CENTER)
_CELLB  = _style("NLCB", fontSize=7,  fontName="Helvetica-Bold",
                 textColor=_NAVY, alignment=TA_CENTER)
_NOTE   = _style("NLN",  fontSize=6,  fontName="Helvetica",
                 textColor=_SLATE, alignment=TA_CENTER)
_LABEL  = _style("NLL",  fontSize=7,  fontName="Helvetica-Bold",
                 textColor=_SLATE)
_VAL    = _style("NLV",  fontSize=8,  fontName="Helvetica",
                 textColor=_NAVY)


# ── Geometry ──────────────────────────────────────────────────────────────────

def _bearing(lat1, lon1, lat2, lon2):
    """True bearing in degrees from point 1 to point 2."""
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2)
    y = (math.cos(lat1) * math.sin(lat2)
         - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _distance_nm(lat1, lon1, lat2, lon2):
    """Haversine distance in nm."""
    R    = 3440.1
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _wind_correction(tas_kt, wd_true, ws_kt, tc_true):
    """
    Compute wind correction angle (WCA) and ground speed (GS).
    Returns (wca_deg, gs_kt). WCA positive = right correction.
    """
    if not ws_kt or not tas_kt:
        return 0, tas_kt or 0
    # Convert to radians
    tc_r  = math.radians(tc_true)
    wd_r  = math.radians(wd_true)
    # Wind vector components (FROM direction → TO direction of wind)
    wx = ws_kt * math.sin(wd_r)  # east component
    wy = ws_kt * math.cos(wd_r)  # north component
    # Sin of WCA
    sin_wca = (wx * math.cos(tc_r) - wy * math.sin(tc_r)) / tas_kt
    sin_wca = max(-1.0, min(1.0, sin_wca))
    wca = math.degrees(math.asin(sin_wca))
    # Ground speed
    gs = (tas_kt * math.cos(math.radians(wca))
          - (wy * math.cos(tc_r) + wx * math.sin(tc_r)))
    return round(wca, 1), max(round(gs), 1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mag_var(lat, lon):
    """
    Very rough magnetic variation (degrees west, positive).
    Adequate for planning; pilot must verify on sectional.
    """
    # Simplified: ~1° west per 100 nm west of ~80°W, calibrated to US east coast
    # Real impl would use World Magnetic Model — this is a planning stub
    return round((lon + 80) * -0.4 + 5, 1)   # rough West US ~14° W, East US ~5° W


def _banner(text, bg=_NAVY):
    tbl = Table([[Paragraph(text, _TITLE)]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _kv_row(pairs, widths):
    """Single-row summary table with label/value pairs."""
    cells = []
    for lbl, val in pairs:
        cells.append(Paragraph(f"<b>{lbl}</b>", _LABEL))
        cells.append(Paragraph(str(val), _VAL))
    tbl = Table([cells], colWidths=widths)
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("BACKGROUND",    (0, 0), (-1, -1), _LIGHT),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    return tbl


# ── Main generator ────────────────────────────────────────────────────────────

def generate_navlog(brief, aircraft=None, waypoints=None, flight_rules="VFR"):
    """
    Generate a VFR navigation log PDF.

    Parameters
    ----------
    brief        : dict from insights.get_preflight_brief()
    aircraft     : dict from aircraft.get_aircraft() or None
    waypoints    : list of dicts {name, lat, lon} for multi-leg IFR routes.
                   If None, single leg origin→dest is generated.
    flight_rules : "VFR" | "IFR" — layout identical; reserved for future IFR fields

    Returns
    -------
    bytes — PDF ready for st.download_button
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.4 * inch, rightMargin=0.4 * inch,
        topMargin=0.4 * inch,  bottomMargin=0.4 * inch,
    )
    W = letter[0] - 0.8 * inch   # usable width

    origin     = brief.get("origin_icao", "???")
    dest       = brief.get("dest_icao",   "???")
    o_apt      = brief.get("origin_apt")  or {}
    d_apt      = brief.get("dest_apt")    or {}
    o_ass      = brief.get("origin_assess") or {}
    cruise_alt = brief.get("cruise_alt_ft", 3500)
    winds_aloft = brief.get("winds_aloft") or {}

    o_lat = o_apt.get("lat"); o_lon = o_apt.get("lon")
    d_lat = d_apt.get("lat"); d_lon = d_apt.get("lon")

    # ── Build legs ────────────────────────────────────────────────────────────
    # Each leg: {from_name, to_name, lat1, lon1, lat2, lon2}
    legs = []
    if waypoints:
        pts = ([{"name": origin, "lat": o_lat, "lon": o_lon}]
               + waypoints
               + [{"name": dest,   "lat": d_lat, "lon": d_lon}])
        for i in range(len(pts) - 1):
            legs.append({
                "from_name": pts[i]["name"],
                "to_name":   pts[i + 1]["name"],
                "lat1": pts[i]["lat"],     "lon1": pts[i]["lon"],
                "lat2": pts[i + 1]["lat"], "lon2": pts[i + 1]["lon"],
            })
    else:
        legs = [{
            "from_name": origin,
            "to_name":   dest,
            "lat1": o_lat, "lon1": o_lon,
            "lat2": d_lat, "lon2": d_lon,
        }]

    # ── Aircraft performance ──────────────────────────────────────────────────
    tas_kt = aircraft.get("cruise_ktas", 100) if aircraft else 100
    fuel_burn = aircraft.get("fuel_burn_gph", 8) if aircraft else 8
    ac_display = aircraft.get("display", "Aircraft") if aircraft else "Aircraft"

    # Winds aloft — pick closest altitude bucket
    w_dir = w_spd = None
    for bucket_alt in [3000, 6000, 9000]:
        key = str(bucket_alt)
        if key in winds_aloft:
            entry = winds_aloft[key]
            w_dir = entry.get("dir"); w_spd = entry.get("spd")
            break

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    hdr_data = [[
        Paragraph("VFR NAVIGATION LOG", _TITLE),
        Paragraph(f"{origin}  →  {dest}", _TITLE),
        Paragraph(str(_date.today()), _TITLE),
    ]]
    hdr_tbl = Table(hdr_data, colWidths=[W * 0.33, W * 0.34, W * 0.33])
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 4))

    # ── Flight summary row ────────────────────────────────────────────────────
    wd_str = f"{w_dir:03d}° / {w_spd} kt" if w_dir and w_spd else "N/A"
    alt_str = f"{cruise_alt:,} ft MSL"
    story.append(_kv_row(
        [
            ("Aircraft:",    ac_display),
            ("TAS:",         f"{tas_kt} kt"),
            ("Cruise Alt:",  alt_str),
            ("Winds Aloft:", wd_str),
            ("Fuel Burn:",   f"{fuel_burn} gph"),
        ],
        widths=[0.65*inch, 1.35*inch, 0.4*inch, 0.65*inch,
                0.75*inch, 1.05*inch, 0.85*inch, 1.3*inch,
                0.7*inch, 0.6*inch],
    ))
    story.append(Spacer(1, 8))

    # ── Nav log table ─────────────────────────────────────────────────────────
    col_labels = [
        "CHECKPOINT", "TC\n(°True)", "MC\n(°Mag)", "DIST\n(nm)",
        "TAS\n(kt)", "WD/WS", "WCA\n(°)", "MH\n(°Mag)", "GS\n(kt)",
        "ETE\n(min)", "ETA\n(UTC)", "ATA\n(UTC)", "FUEL\nREM (gal)",
    ]
    col_w = [
        1.2*inch,   # checkpoint
        0.42*inch,  # TC
        0.42*inch,  # MC
        0.38*inch,  # dist
        0.38*inch,  # TAS
        0.55*inch,  # WD/WS
        0.38*inch,  # WCA
        0.42*inch,  # MH
        0.38*inch,  # GS
        0.38*inch,  # ETE
        0.5*inch,   # ETA
        0.5*inch,   # ATA
        0.55*inch,  # fuel rem
    ]
    # Sanity-clip to usable width
    total_w = sum(col_w)
    if total_w > W:
        scale = W / total_w
        col_w = [c * scale for c in col_w]

    header_row = [Paragraph(lbl, _HDR) for lbl in col_labels]
    data_rows  = [header_row]

    cum_time_min = 0
    fuel_used    = 0

    # Determine magnetic variation from origin if available
    mag_var = 0
    if o_lat and o_lon:
        mag_var = _mag_var(o_lat, o_lon)

    for leg in legs:
        lat1, lon1 = leg.get("lat1"), leg.get("lon1")
        lat2, lon2 = leg.get("lat2"), leg.get("lon2")

        if all(v is not None for v in [lat1, lon1, lat2, lon2]):
            tc      = _bearing(lat1, lon1, lat2, lon2)
            dist    = _distance_nm(lat1, lon1, lat2, lon2)
            wca, gs = _wind_correction(tas_kt, w_dir or 0, w_spd or 0, tc)
            mc      = (tc + mag_var + 360) % 360
            mh      = (mc + wca + 360) % 360
            ete_min = round(dist / gs * 60) if gs else 0
        else:
            tc = mc = mh = wca = gs = ete_min = dist = 0

        cum_time_min += ete_min
        fuel_used    += (ete_min / 60) * fuel_burn
        fuel_rem      = ((aircraft.get("fuel_usable_gal", 0) if aircraft else 0)
                         - fuel_used)

        wd_cell = f"{w_dir:03d}°/{w_spd}kt" if w_dir and w_spd else "—"

        row = [
            Paragraph(f"{leg['from_name']} → {leg['to_name']}", _CELLB),
            Paragraph(f"{tc:.0f}°" if tc else "—", _CELL),
            Paragraph(f"{mc:.0f}°" if mc else "—", _CELL),
            Paragraph(str(dist) if dist else "—", _CELL),
            Paragraph(str(tas_kt), _CELL),
            Paragraph(wd_cell, _NOTE),
            Paragraph(f"{wca:+.1f}°" if wca else "—", _CELL),
            Paragraph(f"{mh:.0f}°" if mh else "—", _CELL),
            Paragraph(str(gs) if gs else "—", _CELL),
            Paragraph(str(ete_min) if ete_min else "—", _CELL),
            Paragraph("_____", _NOTE),   # fill in at flight time
            Paragraph("_____", _NOTE),
            Paragraph(f"{fuel_rem:.1f}" if aircraft else "—", _CELL),
        ]
        data_rows.append(row)

    # Blank "fill-in" rows for additional checkpoints
    blank = [Paragraph("", _CELL)] * len(col_labels)
    for _ in range(max(4, 8 - len(legs))):
        data_rows.append(blank)

    # Totals row
    total_dist = sum(
        _distance_nm(lg["lat1"], lg["lon1"], lg["lat2"], lg["lon2"])
        for lg in legs
        if all(v is not None for v in [lg.get("lat1"), lg.get("lon1"),
                                       lg.get("lat2"), lg.get("lon2")])
    )
    total_row = [
        Paragraph("<b>TOTALS</b>", _CELLB),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
        Paragraph(f"<b>{total_dist}</b>", _CELLB),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
        Paragraph(f"<b>{cum_time_min}</b>", _CELLB),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
        Paragraph("", _CELL),
    ]
    data_rows.append(total_row)

    nav_tbl = Table(data_rows, colWidths=col_w, repeatRows=1)
    nav_tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0, 0),  (-1, 0),  _NAVY),
        ("TOPPADDING",    (0, 0),  (-1, 0),  3),
        ("BOTTOMPADDING", (0, 0),  (-1, 0),  3),
        # Data rows
        ("BACKGROUND",    (0, 1),  (-1, -2), _WHITE),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [_WHITE, _LIGHT]),
        # Totals row
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        # Grid
        ("GRID",          (0, 0),  (-1, -1), 0.4, _BORDER),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 1),  (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1),  (-1, -1), 6),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 2),
    ]))
    story.append(nav_tbl)
    story.append(Spacer(1, 8))

    # ── Fuel planning box ─────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    story.append(Spacer(1, 4))

    if aircraft:
        usable    = aircraft.get("fuel_usable_gal", 0)
        reserve   = 5.0
        trip_fuel = round(fuel_used, 1)
        total_req = round(trip_fuel + reserve, 1)
        endurance = round(usable / fuel_burn, 1) if fuel_burn else 0

        fuel_data = [
            [
                Paragraph("<b>FUEL PLANNING</b>", _LABEL),
                Paragraph(f"Trip fuel: <b>{trip_fuel} gal</b>", _VAL),
                Paragraph(f"Reserve (45 min): <b>{reserve} gal</b>", _VAL),
                Paragraph(f"Total required: <b>{total_req} gal</b>", _VAL),
                Paragraph(f"Usable on board: <b>{usable} gal</b>", _VAL),
                Paragraph(
                    f"Endurance (full): <b>{endurance} hr</b>  —  "
                    + ("<b style='color:#15803d'>ADEQUATE</b>"
                       if usable >= total_req
                       else "<b style='color:#991b1b'>CHECK FUEL</b>"),
                    _VAL,
                ),
            ]
        ]
        fuel_col_w = [1.3*inch, 1.0*inch, 1.3*inch, 1.2*inch, 1.2*inch, 1.8*inch]
        fuel_tbl = Table(fuel_data, colWidths=fuel_col_w)
        fuel_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), _LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(fuel_tbl)
        story.append(Spacer(1, 6))

    # ── Weather summary ───────────────────────────────────────────────────────
    o_ass = brief.get("origin_assess") or {}
    d_ass = brief.get("dest_assess")   or {}

    wx_pairs = []
    if o_ass.get("altimeter"):
        wx_pairs.append(("Altimeter (orig):", f'{float(o_ass["altimeter"]):.2f}" Hg'))
    if o_ass.get("wind_dir") is not None and o_ass.get("wind_kt") is not None:
        wx_pairs.append(("Winds (orig):",
                         f'{o_ass["wind_dir"]:03d}° @ {o_ass["wind_kt"]} kt'))
    if d_ass.get("wind_dir") is not None and d_ass.get("wind_kt") is not None:
        wx_pairs.append(("Winds (dest):",
                         f'{d_ass["wind_dir"]:03d}° @ {d_ass["wind_kt"]} kt'))
    if o_ass.get("best_runway"):
        wx_pairs.append(("Active Rwy (orig):", o_ass["best_runway"]))
    if d_ass.get("best_runway"):
        wx_pairs.append(("Active Rwy (dest):", d_ass["best_runway"]))
    hazards = brief.get("hazards") or []
    if hazards:
        wx_pairs.append(("Hazards:", f"{len(hazards)} active — see in-flight guide"))

    if wx_pairs:
        row_cells = []
        row_widths = []
        for lbl, val in wx_pairs[:6]:
            row_cells += [Paragraph(f"<b>{lbl}</b>", _LABEL),
                          Paragraph(val, _VAL)]
            row_widths += [0.9*inch, 1.0*inch]
        # pad to fill row
        while len(row_cells) < 12:
            row_cells.append(Paragraph("", _CELL))
            row_widths.append(0.9*inch)
        wx_tbl = Table([row_cells[:12]], colWidths=row_widths[:12])
        wx_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, _BORDER),
        ]))
        story.append(wx_tbl)
        story.append(Spacer(1, 4))

    # ── Footer note ───────────────────────────────────────────────────────────
    footer_style = _style("NLF", fontSize=6, fontName="Helvetica",
                          textColor=_SLATE, alignment=TA_CENTER)
    story.append(Paragraph(
        "Verify all headings, distances, and frequencies against current sectional chart and AFD. "
        "Magnetic variation is estimated — confirm on sectional. "
        "File a VFR flight plan with FSS (1-800-WX-BRIEF) before departure.",
        footer_style,
    ))

    doc.build(story)
    return buf.getvalue()
