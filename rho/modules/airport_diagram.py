"""
Rho — airport runway diagram.

Draws a north-up, to-scale runway layout for an airport, highlighting the
active runway end, wind, and headwind/crosswind components.

Geometry source: OurAirports runways.csv (threshold lat/lon, true headings,
displaced thresholds, closed flag). Cached module-level, ~4 MB, once per process.
Labels: when FAA runway designators are supplied (from airport.get_runways),
they take priority — OurAirports idents can lag FAA renumbering
(e.g. KVNC 04/22 -> 05/23).

Taxiways, ramps, and hot spots are NOT drawn. Always use the official FAA
airport diagram / Chart Supplement for ground ops.

Usage:
    from rho.modules.airport_diagram import (
        get_airport_layout, pick_active_end, generate_airport_diagram_png)
    layout = get_airport_layout("KSRQ", faa_runways=apt["runways"])
    active = pick_active_end(layout, best_runway="04/22", wind_dir=60, wind_kt=6)
    png    = generate_airport_diagram_png(layout, active, wind_dir=60, wind_kt=6,
                                          title="KSRQ", subtitle="Elev 30 ft")
"""

import io
import csv
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, FancyArrowPatch

import requests

_RWY_URLS = [
    "https://ourairports.com/data/runways.csv",
    "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/runways.csv",
]

_by_icao = {}
_loaded = False

_FT_PER_DEG_LAT = 364567.0   # 60 nm * 6076.1 ft


# ── Data loading ──────────────────────────────────────────────────────────────

def _load(csv_text=None):
    """Download + index OurAirports runways.csv (or parse supplied text)."""
    global _by_icao, _loaded
    if _loaded and csv_text is None:
        return
    text = csv_text
    if text is None:
        for url in _RWY_URLS:
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                text = resp.text
                break
            except Exception:
                continue
    if text:
        idx = {}
        for row in csv.DictReader(io.StringIO(text)):
            ident = (row.get("airport_ident") or "").strip().upper()
            if ident:
                idx.setdefault(ident, []).append(row)
        _by_icao = idx
    _loaded = True


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rwy_num(ident):
    """'14L' -> (14, 'L'); 'H1' -> (None, '')."""
    digits = "".join(c for c in (ident or "") if c.isdigit())
    suffix = "".join(c for c in (ident or "") if c in "LRC")
    return (int(digits) if digits else None, suffix)


def _num_diff(a, b):
    d = abs(a - b) % 36
    return min(d, 36 - d)


def _bearing(lat1, lon1, lat2, lon2):
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dlo = math.radians(lon2 - lon1)
    x = math.sin(dlo) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def get_airport_layout(icao, faa_runways=None):
    """
    Return a layout dict for the airport, or None if no geometry is available:
        {
          icao, lat0, lon0,
          runways: [ {
              designator, length_ft, width_ft, surface, lighted, closed,
              ends: [ {ident, lat, lon, heading_true, displaced_ft}, {...} ]
          } ]
        }
    """
    _load()
    icao = (icao or "").upper().strip()
    rows = _by_icao.get(icao) or []

    runways = []
    for r in rows:
        le_lat, le_lon = _f(r.get("le_latitude_deg")), _f(r.get("le_longitude_deg"))
        he_lat, he_lon = _f(r.get("he_latitude_deg")), _f(r.get("he_longitude_deg"))
        if None in (le_lat, le_lon, he_lat, he_lon):
            continue   # helipads / runways without surveyed thresholds
        le_hdg = _f(r.get("le_heading_degT"))
        he_hdg = _f(r.get("he_heading_degT"))
        if le_hdg is None:
            le_hdg = _bearing(le_lat, le_lon, he_lat, he_lon)
        if he_hdg is None:
            he_hdg = (le_hdg + 180) % 360
        runways.append({
            "designator": f"{r.get('le_ident','')}/{r.get('he_ident','')}",
            "length_ft":  int(_f(r.get("length_ft")) or 0) or None,
            "width_ft":   int(_f(r.get("width_ft")) or 0) or None,
            "surface":    (r.get("surface") or "").strip(),
            "lighted":    (r.get("lighted") or "0").strip() == "1",
            "closed":     (r.get("closed") or "0").strip() == "1",
            "ends": [
                {"ident": (r.get("le_ident") or "").strip(), "lat": le_lat, "lon": le_lon,
                 "heading_true": le_hdg, "displaced_ft": _f(r.get("le_displaced_threshold_ft")) or 0},
                {"ident": (r.get("he_ident") or "").strip(), "lat": he_lat, "lon": he_lon,
                 "heading_true": he_hdg, "displaced_ft": _f(r.get("he_displaced_threshold_ft")) or 0},
            ],
        })

    if not runways:
        return None

    # ── Prefer FAA designators / dimensions where they match ─────────────────
    if faa_runways:
        used = set()
        for rw in runways:
            le_num, le_sfx = _rwy_num(rw["ends"][0]["ident"])
            if le_num is None:
                continue
            best, best_d = None, None
            for i, fr in enumerate(faa_runways):
                if i in used:
                    continue
                parts = (fr.get("designator") or "").split("/")
                if len(parts) != 2:
                    continue
                for flip in (False, True):
                    a, b = (parts[1], parts[0]) if flip else (parts[0], parts[1])
                    a_num, a_sfx = _rwy_num(a)
                    if a_num is None or (le_sfx and a_sfx and le_sfx != a_sfx):
                        continue
                    d = _num_diff(le_num, a_num)
                    if d <= 2 and (best_d is None or d < best_d):
                        best, best_d = (i, a.strip(), b.strip(), fr), d
            if best:
                i, a, b, fr = best
                used.add(i)
                rw["ends"][0]["ident"] = a
                rw["ends"][1]["ident"] = b
                rw["designator"] = fr.get("designator") or f"{a}/{b}"
                rw["closed"] = False   # FAA lists it -> treat as open
                if fr.get("length_ft"):
                    rw["length_ft"] = fr["length_ft"]
                if fr.get("width_ft"):
                    rw["width_ft"] = fr["width_ft"]
                if fr.get("surface"):
                    rw["surface"] = fr["surface"]

    lats = [e["lat"] for rw in runways for e in rw["ends"]]
    lons = [e["lon"] for rw in runways for e in rw["ends"]]
    return {
        "icao": icao,
        "lat0": (min(lats) + max(lats)) / 2,
        "lon0": (min(lons) + max(lons)) / 2,
        "runways": runways,
    }


# ── Active runway + wind components ──────────────────────────────────────────

def wind_components(wind_dir, wind_kt, heading_true):
    """Return (headwind_kt, crosswind_kt, side) — headwind negative = tailwind."""
    if wind_dir is None or not wind_kt:
        return 0.0, 0.0, ""
    ang = math.radians((wind_dir - heading_true + 540) % 360 - 180)
    hw = wind_kt * math.cos(ang)
    xw = wind_kt * math.sin(ang)
    return round(hw, 1), round(abs(xw), 1), ("R" if xw > 0.05 else "L" if xw < -0.05 else "")


def pick_active_end(layout, best_runway=None, wind_dir=None, wind_kt=None):
    """
    Choose the runway end most aligned with the wind.
    If best_runway (e.g. '04/22') is given, restrict to that runway.
    Returns dict {ident, designator, heading_true, headwind, crosswind, side,
                  length_ft, width_ft} or None.
    """
    if not layout:
        return None
    cands = []
    for rw in layout["runways"]:
        if rw["closed"]:
            continue
        if best_runway and rw["designator"].replace(" ", "") != best_runway.replace(" ", ""):
            continue
        for e in rw["ends"]:
            cands.append((rw, e))
    if not cands and best_runway:
        return pick_active_end(layout, None, wind_dir, wind_kt)
    if not cands:
        return None

    def score(c):
        hw, xw, _ = wind_components(wind_dir, wind_kt or 0, c[1]["heading_true"])
        # Prefer most headwind; with calm wind prefer the longest runway
        return (hw if wind_kt else 0, c[0].get("length_ft") or 0)

    rw, e = max(cands, key=score)
    hw, xw, side = wind_components(wind_dir, wind_kt or 0, e["heading_true"])
    return {
        "ident": e["ident"], "designator": rw["designator"],
        "heading_true": e["heading_true"],
        "headwind": hw, "crosswind": xw, "side": side,
        "length_ft": rw.get("length_ft"), "width_ft": rw.get("width_ft"),
    }


def components_label(active, wind_kt):
    """'Rwy 4: HW 5 kt · XW 2 kt from R' style string."""
    if not active:
        return ""
    if not wind_kt:
        return f"Rwy {active['ident']}: calm"
    hw = active["headwind"]
    hw_s = f"HW {hw:.0f} kt" if hw >= 0 else f"TAILWIND {abs(hw):.0f} kt"
    xw_s = f"XW {active['crosswind']:.0f} kt"
    if active["side"] and active["crosswind"] >= 1:
        xw_s += f" from {'right' if active['side'] == 'R' else 'left'}"
    return f"Rwy {active['ident']}: {hw_s} · {xw_s}"


# ── Rendering ────────────────────────────────────────────────────────────────

def _xy(lat, lon, lat0, lon0):
    x = (lon - lon0) * _FT_PER_DEG_LAT * math.cos(math.radians(lat0))
    y = (lat - lat0) * _FT_PER_DEG_LAT
    return x, y


def generate_airport_diagram_png(layout, active=None, wind_dir=None, wind_kt=None,
                                 title=None, subtitle=None,
                                 width_in=3.6, height_in=3.6, dark=False, dpi=170):
    """
    Render the runway layout as PNG bytes. Returns None on failure / no layout.
    """
    if not layout:
        return None
    try:
        return _render(layout, active, wind_dir, wind_kt, title, subtitle,
                       width_in, height_in, dark, dpi)
    except Exception:
        plt.close("all")
        return None


def _seg_dist(p, a, b):
    ax_, ay_ = b[0] - a[0], b[1] - a[1]
    L2 = ax_ * ax_ + ay_ * ay_ or 1.0
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax_ + (p[1] - a[1]) * ay_) / L2))
    return math.hypot(p[0] - a[0] - t * ax_, p[1] - a[1] - t * ay_)


def _render(layout, active, wind_dir, wind_kt, title, subtitle,
            width_in, height_in, dark, dpi):
    lat0, lon0 = layout["lat0"], layout["lon0"]

    bg      = "#0f172a" if dark else "white"
    fg      = "#e2e8f0" if dark else "#0f172a"
    muted   = "#94a3b8" if dark else "#64748b"
    rwy_c   = "#64748b" if dark else "#334155"
    act_c   = "#22c55e" if dark else "#15803d"
    closed_c = "#475569" if dark else "#cbd5e1"
    wind_c  = "#f97316"

    # Geometry in feet
    geo = []
    xs, ys = [], []
    for rw in layout["runways"]:
        a = _xy(rw["ends"][0]["lat"], rw["ends"][0]["lon"], lat0, lon0)
        b = _xy(rw["ends"][1]["lat"], rw["ends"][1]["lon"], lat0, lon0)
        geo.append((rw, a, b))
        xs += [a[0], b[0]]
        ys += [a[1], b[1]]

    span = max(max(xs) - min(xs), max(ys) - min(ys), 2500.0)
    pad = span * 0.24
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    half = span / 2 + pad

    fig = plt.figure(figsize=(width_in, height_in), dpi=dpi)
    fig.patch.set_facecolor(bg)
    top = 0.86 if (title or subtitle) else 0.98
    ax = fig.add_axes([0.02, 0.02, 0.96, top - 0.02])
    ax.set_facecolor(bg)
    ax.set_aspect("equal")
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)
    ax.axis("off")

    if title:
        fig.text(0.03, 0.955, title, color=fg, fontsize=10, fontweight="bold",
                 ha="left", va="center")
    if subtitle:
        fig.text(0.03, 0.905, subtitle, color=muted, fontsize=6.5, ha="left", va="center")

    min_w = span * 0.02   # keep narrow runways visible
    active_ident = (active or {}).get("ident")
    active_desig = (active or {}).get("designator")

    label_fs = 7.5
    for rw, a, b in geo:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L          # unit along runway (le -> he)
        nx, ny = -uy, ux                 # unit normal
        w = max(rw.get("width_ft") or 100, min_w) / 2
        is_active = (rw["designator"] == active_desig) and not rw["closed"]
        color = closed_c if rw["closed"] else (act_c if is_active else rwy_c)

        poly = [
            (a[0] + nx * w, a[1] + ny * w), (b[0] + nx * w, b[1] + ny * w),
            (b[0] - nx * w, b[1] - ny * w), (a[0] - nx * w, a[1] - ny * w),
        ]
        ax.add_patch(MplPolygon(poly, closed=True, fc=color, ec=color, lw=0.5, zorder=3))

        if rw["closed"]:
            # X marks at each third
            for t in (0.25, 0.75):
                mx, my = a[0] + dx * t, a[1] + dy * t
                s = w * 2.2
                for sgn in (1, -1):
                    ax.plot([mx - ux * s - sgn * nx * s, mx + ux * s + sgn * nx * s],
                            [my - uy * s - sgn * ny * s, my + uy * s + sgn * ny * s],
                            color="#ef4444", lw=1.4, zorder=4)
        else:
            # Centerline
            ax.plot([a[0] + ux * L * 0.06, b[0] - ux * L * 0.06],
                    [a[1] + uy * L * 0.06, b[1] - uy * L * 0.06],
                    color="white", lw=0.5, ls=(0, (4, 3)), zorder=4, alpha=0.9)
            # Displaced thresholds — white bar across the runway at the displacement
            for end, base, sign in ((rw["ends"][0], a, 1), (rw["ends"][1], b, -1)):
                d = end.get("displaced_ft") or 0
                if d > 0:
                    px, py = base[0] + sign * ux * d, base[1] + sign * uy * d
                    ax.plot([px + nx * w, px - nx * w], [py + ny * w, py - ny * w],
                            color="white", lw=1.6, zorder=5)
                    ax.plot([base[0], px], [base[1], py], color=bg, lw=0.6,
                            ls=(0, (1.5, 1.5)), zorder=5, alpha=0.8)

        # End labels (outside each threshold, upright text)
        off = span * 0.055
        for end, base, sign in ((rw["ends"][0], a, -1), (rw["ends"][1], b, 1)):
            lx, ly = base[0] + sign * ux * off, base[1] + sign * uy * off
            hot = is_active and end["ident"] == active_ident
            ax.text(lx, ly, end["ident"], ha="center", va="center",
                    fontsize=label_fs, fontweight="bold", zorder=7,
                    color="white" if hot else (muted if rw["closed"] else fg),
                    bbox=dict(boxstyle="round,pad=0.22",
                              fc=act_c if hot else bg,
                              ec=act_c if hot else (closed_c if rw["closed"] else rwy_c),
                              lw=0.8))

        # Length x width label along the runway, offset to one side
        if rw.get("length_ft"):
            txt = f"{rw['length_ft']:,} x {rw.get('width_ft') or '?'}"
            if rw["closed"]:
                txt = "CLOSED"
            ang = math.degrees(math.atan2(dy, dx))
            if ang > 90:
                ang -= 180
            if ang < -90:
                ang += 180
            others = [(g[1], g[2]) for g in geo if g[0] is not rw]
            best_t = max((0.3, 0.5, 0.7, 0.2, 0.8),
                         key=lambda t: min([_seg_dist((a[0] + dx * t, a[1] + dy * t), p0, p1)
                                            for p0, p1 in others] or [1e9]))
            mx, my = a[0] + dx * best_t, a[1] + dy * best_t
            o = w + span * 0.035
            ax.text(mx + nx * o, my + ny * o, txt, rotation=ang, rotation_mode="anchor",
                    ha="center", va="center", fontsize=5.6, color=muted, zorder=6)

    # Landing / takeoff direction arrow on the active runway
    if active:
        for rw, a, b in geo:
            if rw["designator"] != active_desig or rw["closed"]:
                continue
            start, end_pt = (a, b) if rw["ends"][0]["ident"] == active_ident else (b, a)
            dx, dy = end_pt[0] - start[0], end_pt[1] - start[1]
            L = math.hypot(dx, dy) or 1.0
            ux, uy = dx / L, dy / L
            nx, ny = -uy, ux
            w = max(rw.get("width_ft") or 100, min_w) / 2
            o = w + span * 0.075
            s = (start[0] - nx * o + ux * L * 0.15, start[1] - ny * o + uy * L * 0.15)
            e = (start[0] - nx * o + ux * L * 0.55, start[1] - ny * o + uy * L * 0.55)
            ax.add_patch(FancyArrowPatch(s, e, arrowstyle="-|>", mutation_scale=9,
                                         color=act_c, lw=1.4, zorder=6))

    # North arrow (bottom-right, inside plot)
    ax.annotate("", xy=(0.95, 0.20), xytext=(0.95, 0.09), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=fg, lw=1.0, mutation_scale=8))
    ax.text(0.95, 0.235, "N", transform=ax.transAxes, ha="center", va="bottom",
            fontsize=6.5, fontweight="bold", color=fg)

    # Wind indicator — header strip, top-right (outside the runway area)
    if wind_dir is not None and wind_kt:
        to = math.radians((wind_dir + 180) % 360)
        cxw, cyw = 0.90, 0.93
        rx, ry = 0.045, 0.045 * width_in / height_in
        sx, sy = cxw - math.sin(to) * rx, cyw - math.cos(to) * ry
        ex, ey = cxw + math.sin(to) * rx, cyw + math.cos(to) * ry
        fig.patches.append(FancyArrowPatch((sx, sy), (ex, ey), transform=fig.transFigure,
                                           arrowstyle="-|>", mutation_scale=10,
                                           color=wind_c, lw=1.8))
        fig.text(cxw - 0.07, 0.955, "WIND", color=muted, fontsize=5.5, ha="right", va="center")
        fig.text(cxw - 0.07, 0.905, f"{int(wind_dir):03d}° @ {int(wind_kt)} kt", color=wind_c,
                 fontsize=7, fontweight="bold", ha="right", va="center")
    elif wind_kt == 0 and wind_dir is not None:
        fig.text(0.97, 0.93, "WIND CALM", color=wind_c, fontsize=7,
                 fontweight="bold", ha="right", va="center")

    # Wind components caption (bottom)
    comp = components_label(active, wind_kt)
    if comp:
        ax.text(0.5, 0.025, comp, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=6.8, color=act_c, fontweight="bold")

    # Scale bar (bottom-left)
    bar = 1000 if span < 7000 else 2000
    x0 = cx - half + span * 0.06
    y0 = cy - half + span * 0.14
    ax.plot([x0, x0 + bar], [y0, y0], color=fg, lw=1.2, zorder=6)
    for xx in (x0, x0 + bar):
        ax.plot([xx, xx], [y0 - span * 0.012, y0 + span * 0.012], color=fg, lw=1.0, zorder=6)
    ax.text(x0 + bar / 2, y0 + span * 0.025, f"{bar:,} ft", ha="center", va="bottom",
            fontsize=5.5, color=muted)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=bg, dpi=dpi)
    plt.close(fig)
    return buf.getvalue()
