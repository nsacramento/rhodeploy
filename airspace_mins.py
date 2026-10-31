"""
Rho — VFR weather minimums by airspace (14 CFR 91.155, 61.89).

    MINIMUMS                      table rows (for the app, kneeboard, and reference card)
    generate_vfr_mins_png(...)    classic airspace cross-section diagram, optional highlight
    surface_class(airspaces, lat, lon)
                                  class of the surface airspace at an airport (B/C/D/E) or None
    check_vfr_minimums(brief)     -> (factors, rows, highlight_classes)
                                  today's weather vs the minimums for each airport + cruise

All checks are conservative planning aids. The sectional and the regulations govern.
"""

import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MplPolygon

# ── The rules (91.155) ────────────────────────────────────────────────────────

_STD = "500 below · 1,000 above · 2,000 horizontal"
_HIGH = "1,000 below · 1,000 above · 1 sm horizontal"

MINIMUMS = [
    {"cls": "A", "where": "18,000 MSL – FL600",           "vis": "—",       "clouds": "IFR only"},
    {"cls": "B", "where": "Surface – ~10,000 MSL",         "vis": "3 sm",    "clouds": "Clear of clouds"},
    {"cls": "C", "where": "Surface – ~4,000 AGL",          "vis": "3 sm",    "clouds": _STD},
    {"cls": "D", "where": "Surface – ~2,500 AGL",          "vis": "3 sm",    "clouds": _STD},
    {"cls": "E", "where": "Below 10,000 MSL",              "vis": "3 sm",    "clouds": _STD},
    {"cls": "E", "where": "At or above 10,000 MSL",        "vis": "5 sm",    "clouds": _HIGH},
    {"cls": "G", "where": "1,200 AGL or below — day",      "vis": "1 sm",    "clouds": "Clear of clouds"},
    {"cls": "G", "where": "1,200 AGL or below — night",    "vis": "3 sm",    "clouds": _STD + " ¹"},
    {"cls": "G", "where": "Above 1,200 AGL, below 10,000 MSL — day",   "vis": "1 sm", "clouds": _STD},
    {"cls": "G", "where": "Above 1,200 AGL, below 10,000 MSL — night", "vis": "3 sm", "clouds": _STD},
    {"cls": "G", "where": "Above 1,200 AGL, at or above 10,000 MSL",   "vis": "5 sm", "clouds": _HIGH},
]

NOTES = [
    "**Surface areas** of Class B, C, D, or E: ceiling at least **1,000 ft** and ground visibility "
    "at least **3 sm** to take off, land, or enter the traffic pattern — otherwise Special VFR (91.155(c),(d)).",
    "**Student pilots solo** (61.89): at least **3 sm** visibility by day, **5 sm** at night, and "
    "visual reference to the surface. Your CFI's endorsement limits may be stricter.",
    "¹ Class G at night, 1,200 AGL or below: 1 sm and clear of clouds is allowed when operating in the "
    "traffic pattern within ½ mile of the runway.",
    "Memory aid for C, D, E below 10,000: **3-152** — 3 sm, 1,000 above, 500 below, 2,000 horizontal.",
]

_REQ_BELOW = {"B": 0, "C": 500, "D": 500, "E": 500, "G": 0}   # day, ≤ 1,200 AGL, below 10,000 MSL

_CLS_FILL = {"A": "#e2e8f0", "B": "#bfdbfe", "C": "#f5d0fe", "D": "#bae6fd", "E": "#fce7f3", "G": "#f8fafc"}
_CLS_EDGE = {"A": "#64748b", "B": "#1d4ed8", "C": "#a21caf", "D": "#0369a1", "E": "#db2777", "G": "#94a3b8"}


# ── Diagram ───────────────────────────────────────────────────────────────────

def generate_vfr_mins_png(highlight=None, width_in=10.0, height_in=5.6, dpi=170):
    """
    Classic airspace cross-section with VFR minimums in each class.
    highlight: iterable of class letters to emphasize (others are faded). None = all normal.
    Returns PNG bytes or None.
    """
    try:
        return _draw(set(highlight) if highlight else None, width_in, height_in, dpi)
    except Exception:
        plt.close("all")
        return None


def _draw(hl, width_in, height_in, dpi):
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=dpi)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    def alpha(c):
        return 1.0 if (hl is None or c in hl) else 0.28

    def box(x0, y0, x1, y1, c, dashed=False, z=2):
        a = alpha(c)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=_CLS_FILL[c], ec=_CLS_EDGE[c],
                               lw=1.4 if not dashed else 1.2, ls="--" if dashed else "-",
                               alpha=a, zorder=z))

    def label(x, y, c, title, body, size=7.2, ha="center"):
        a = alpha(c)
        ax.text(x, y, title, ha=ha, va="bottom", fontsize=size + 1.6, fontweight="bold",
                color=_CLS_EDGE[c], alpha=a, zorder=6)
        ax.text(x, y - 0.6, body, ha=ha, va="top", fontsize=size, color="#0f172a",
                alpha=max(a, 0.35), zorder=6, linespacing=1.25)

    def shape(pts, c, z=3):
        a = alpha(c)
        ax.add_patch(MplPolygon(pts, closed=True, fc=_CLS_FILL[c], ec=_CLS_EDGE[c], lw=1.5,
                                alpha=a, zorder=z))

    # Altitude scale (schematic, not to scale)
    Y_SFC, Y_700, Y_1200, Y_10K, Y_18K, Y_TOP = 6, 16, 25, 62, 82, 97
    box(0, Y_1200, 100, Y_18K, "E", z=1)          # Class E below 18,000 (above G)
    box(0, Y_10K, 100, Y_18K, "E", z=1)           # Class E at/above 10,000
    box(0, Y_SFC, 100, Y_1200, "G", z=1)          # Class G surface – 1,200 AGL
    box(0, Y_18K, 100, Y_TOP, "A", z=1)           # Class A

    # Class B — upside-down wedding cake
    shape([(10, Y_SFC), (20, Y_SFC), (20, 32), (24.5, 32), (24.5, 44), (29.5, 44), (29.5, Y_10K),
           (0.5, Y_10K), (0.5, 44), (5.5, 44), (5.5, 32), (10, 32)], "B")
    label(15, 56, "B", "CLASS B", "3 sm\nclear of clouds")

    # Class C — surface core + shelf
    shape([(38, Y_SFC), (46, Y_SFC), (46, 30), (52, 30), (52, 44), (32, 44), (32, 30), (38, 30)], "C")
    label(42, 40.2, "C", "CLASS C", "3 sm\n500 below · 1,000 above\n2,000 horiz")

    # Class D — cylinder
    box(56, Y_SFC, 66, 36, "D", z=3)
    label(61, 32.3, "D", "CLASS D", "3 sm\n500 below\n1,000 above\n2,000 horiz", size=6.6)

    # Non-towered: Class E from 700 AGL, Class E surface area, Class G underneath
    box(70, Y_700, 99.5, Y_1200, "E", z=3)
    box(91, Y_SFC, 98, Y_700, "E", dashed=True, z=4)
    ax.text(94.5, (Y_SFC + Y_700) / 2, "E\nsurface", ha="center", va="center", fontsize=5.8,
            color=_CLS_EDGE["E"], alpha=alpha("E"), zorder=6)
    ax.text(98.5, (Y_700 + Y_1200) / 2, "E from 700 AGL", ha="right", va="center", fontsize=6.2,
            color=_CLS_EDGE["E"], alpha=alpha("E"), zorder=6)
    ax.text(71, Y_700 - 1.6, "CLASS G  (≤ 1,200 AGL)", ha="left", va="top",
            fontsize=8, fontweight="bold", color="#475569", alpha=alpha("G"), zorder=6)
    ax.text(71, Y_700 - 5.0, "Day: 1 sm, clear of clouds\nNight: 3 sm, 500 / 1,000 / 2,000",
            ha="left", va="top", fontsize=6.3, color="#0f172a", alpha=alpha("G"), zorder=6,
            linespacing=1.2)

    # Class E / A labels
    label(83, 50, "E", "CLASS E  (below 10,000 MSL)", "3 sm\n500 below · 1,000 above\n2,000 horizontal")
    label(50, 76, "E", "CLASS E  (at or above 10,000 MSL)", "5 sm · 1,000 below · 1,000 above · 1 sm horizontal")
    label(50, 93, "A", "CLASS A  (18,000 MSL – FL600)", "IFR only")

    # Ground + altitude ticks
    ax.plot([0, 100], [Y_SFC, Y_SFC], color="#78350f", lw=2.2, zorder=7)
    for y, t in ((Y_SFC, "SFC"), (Y_700, "700 AGL"), (Y_1200, "1,200 AGL"),
                 (Y_10K, "10,000 MSL"), (Y_18K, "18,000 MSL")):
        ax.text(-0.6, y, t, ha="right", va="center", fontsize=6.4, color="#475569")
        ax.plot([0, 100], [y, y], color="#94a3b8", lw=0.4, ls=":", zorder=0)

    # Airport symbols
    for x, lbl in ((15, "towered (B)"), (42, "towered (C)"), (61, "towered (D)"), (94.5, "non-towered")):
        ax.plot([x - 2, x + 2], [Y_SFC, Y_SFC], color="#0f172a", lw=3.2, zorder=8)
        ax.text(x, Y_SFC - 1.2, lbl, ha="center", va="top", fontsize=5.8, color="#475569")

    ax.text(100, 0.2, "Not to scale. Surface areas need 1,000 ft ceiling + 3 sm to enter the pattern.",
            ha="right", va="bottom", fontsize=6, color="#64748b", style="italic")
    fig.subplots_adjust(left=0.085, right=0.995, top=0.99, bottom=0.03)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# ── Airport surface airspace ─────────────────────────────────────────────────

def _is_surface(asp):
    raw = asp.get("lower_raw")
    if raw is not None:
        try:
            return float(raw) <= 0
        except (TypeError, ValueError):
            pass
    return str(asp.get("lower_ft", "")).upper().strip() in ("SFC", "0", "SURFACE", "GND")


def surface_class(airspaces, lat, lon):
    """Most restrictive surface-based class (B > C > D > E) containing the airport, or None."""
    if lat is None or lon is None or not airspaces:
        return None
    try:
        from shapely.geometry import Point
    except Exception:
        return None
    pt = Point(lon, lat)
    found = set()
    for a in airspaces:
        cls = str(a.get("airspace_class") or "").upper()[:1]
        poly = a.get("polygon")
        if cls not in "BCDE" or poly is None or not _is_surface(a):
            continue
        try:
            if poly.contains(pt):
                found.add(cls)
        except Exception:
            continue
    for c in "BCDE":
        if c in found:
            return c
    return None


# ── Today's check ─────────────────────────────────────────────────────────────

def check_vfr_minimums(brief, comms_o=None, comms_d=None, pattern_agl=1000):
    """
    Compare today's reported weather with VFR minimums.

    Returns (factors, rows, highlight):
      factors   [{level, type, airport, short, detail}] — fed into the go/no-go
      rows      per-airport table rows for display
      highlight set of airspace classes relevant to this flight (for the diagram)
    """
    factors, rows = [], []
    airspaces = brief.get("airspaces") or []
    cruise = brief.get("cruise_alt_ft") or 3500
    highlight = set()

    route = (brief.get("route") or {}).get("direct") or {}
    for p in route.get("airspace_penetrations") or []:
        c = str(p.get("class", "")).upper()[:1]
        if c:
            highlight.add(c)

    legs = [
        (brief.get("origin_icao"), brief.get("origin_apt") or {}, brief.get("origin_assess") or {}, comms_o or {}),
        (brief.get("dest_icao"), brief.get("dest_apt") or {}, brief.get("dest_assess") or {}, comms_d or {}),
    ]
    for icao, apt, a, c in legs:
        elev = apt.get("elevation_ft") or 0
        sc = surface_class(airspaces, apt.get("lat"), apt.get("lon"))
        known = sc is not None
        if not known:
            # No surface polygon found: towered -> at least Class D; otherwise assume E (stricter than G)
            sc = "D" if c.get("has_tower") else "E"
        highlight.add(sc)
        if not known and not c.get("has_tower"):
            highlight.add("G")
        cls_label = f"Class {sc}" + ("" if known else (" (assumed)" if c.get("has_tower") else " or G (assumed E)"))

        ceil = a.get("ceiling_ft")
        vis = a.get("visibility")
        status, notes = "OK", []

        # 1) Basic VFR in a surface area (1,000 ft ceiling, 3 sm)
        if known or c.get("has_tower"):
            if (ceil is not None and ceil < 1000) or (vis is not None and vis < 3):
                status = "BELOW"
                notes.append("below basic VFR for the surface area (needs 1,000 ft ceiling + 3 sm)")

        # 2) Pattern cloud clearance
        need = _REQ_BELOW.get(sc, 500)
        if ceil is not None:
            gap = ceil - pattern_agl
            if gap < need:
                status = "BELOW" if status == "BELOW" else "TIGHT"
                notes.append(f"pattern at {pattern_agl:,} AGL is only {max(gap, 0):,} ft below the "
                             f"ceiling — {cls_label} needs {need:,} ft")
                factors.append({
                    "level": "CAUTION", "type": "VFR minimums", "airport": icao,
                    "short": f"pattern {max(gap, 0):,} ft below clouds (needs {need:,})",
                    "detail": (f"Ceiling {ceil:,} ft AGL. A {pattern_agl:,} ft AGL pattern leaves "
                               f"{max(gap, 0):,} ft below the clouds; {cls_label} requires {need:,} ft below "
                               f"(91.155). You'd have to fly a lower pattern than published — "
                               f"not a student option. Wait or divert."),
                })

            # 3) Cruise altitude vs the ceiling at this airport
            ceil_msl = elev + ceil
            if cruise > ceil_msl - 500:
                notes.append(f"cruise {cruise:,} MSL isn't 500 ft below the ~{ceil_msl:,} MSL ceiling")
                factors.append({
                    "level": "CAUTION", "type": "VFR minimums", "airport": icao,
                    "short": f"cruise {cruise:,} MSL vs ceiling ~{ceil_msl:,} MSL",
                    "detail": (f"Ceiling here is ~{ceil_msl:,} MSL. Cruising at {cruise:,} MSL means flying "
                               f"in or above the clouds near {icao}; VFR needs at least 500 ft below. "
                               f"Plan a lower cruise only if terrain, airspace, and the 1,000/500 "
                               f"minimums allow — or wait."),
                })
                if status == "OK":
                    status = "TIGHT"

        # 4) Student solo visibility
        if vis is not None and vis < 3:
            notes.append("below the 3 sm student solo minimum (61.89)")

        req_vis = "3 sm"
        req_ceiling = "1,000 ft (surface area)" if (known or c.get("has_tower")) else "none (Class G) / check sectional"
        rows.append({
            "airport": icao, "surface": cls_label,
            "required": f"{req_vis} · {need:,} ft below clouds" + (f" · ceiling {req_ceiling}" if "1,000" in req_ceiling else ""),
            "reported": (f"{vis:g} sm" if vis is not None else "? sm") + " · " +
                        (f"ceiling {ceil:,} AGL" if ceil is not None else "no ceiling"),
            "status": status, "notes": "; ".join(notes) or "meets VFR minimums for a standard pattern",
        })

    if cruise > 1200 + max((brief.get("origin_apt") or {}).get("elevation_ft") or 0, 0):
        highlight.add("E")
    return factors, rows, highlight
