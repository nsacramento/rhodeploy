"""
Rho — shared route map generator.

Primary renderer: contextily tile basemap (CartoDB DarkMatter / Positron)
                  + shapely airspace polygons + matplotlib overlays.
Fallback:         plain matplotlib with colored background (no network needed).

Install contextily once:
    pip3 install contextily

Usage:
    from rho.modules.map_utils import generate_route_map_png
    png = generate_route_map_png(
        o_lat, o_lon, d_lat, d_lon,
        "KSRQ", "KSPG",
        airspaces=brief["airspaces"],  # list from get_airspace_near()
        cruise_alt_ft=3500,
        width_in=8.0, height_in=5.5,
        dark=True,                     # False for print/PDF
    )
"""
import io
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

try:
    import contextily as ctx
    _HAS_CTX = True
except ImportError:
    _HAS_CTX = False

# ── Class styling ──────────────────────────────────────────────────────────────
_CLS_COLOR = {
    "B": "#3b82f6",  # blue
    "C": "#a855f7",  # purple
    "D": "#14b8a6",  # teal
    "E": "#94a3b8",  # slate
    "G": "#6b7280",  # gray
}
_CLS_LABEL = {
    "B": "Class B (Bravo)",
    "C": "Class C (Charlie)",
    "D": "Class D (Delta)",
    "E": "Class E",
    "G": "Class G (Uncontrolled)",
}

_ROUTE_COLOR = "#f97316"   # orange — readable on both light and dark tiles


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_route_map_png(
    o_lat, o_lon, d_lat, d_lon,
    origin_icao, dest_icao,
    airspaces=None,
    cruise_alt_ft=3500,
    width_in=8.0,
    height_in=5.5,
    dark=True,
):
    """
    Generate a route overview map as PNG bytes.

    Parameters
    ----------
    o_lat, o_lon    : float — origin airport lat/lon
    d_lat, d_lon    : float — destination airport lat/lon
    origin_icao     : str
    dest_icao       : str
    airspaces       : list[dict] — from get_airspace_near(); each dict may have
                      a shapely Polygon under the key 'polygon'
    cruise_alt_ft   : int — shown as a label in the map corner
    width_in        : figure width in inches
    height_in       : figure height in inches
    dark            : True  → CartoDB DarkMatter tiles + dark chrome (screen)
                      False → CartoDB Positron tiles + light chrome (PDF/print)

    Returns
    -------
    bytes (PNG) or None if rendering fails
    """
    kwargs = dict(
        o_lat=o_lat, o_lon=o_lon, d_lat=d_lat, d_lon=d_lon,
        origin_icao=origin_icao, dest_icao=dest_icao,
        airspaces=airspaces, cruise_alt_ft=cruise_alt_ft,
        width_in=width_in, height_in=height_in, dark=dark,
    )
    if _HAS_CTX:
        try:
            return _render_tiled(**kwargs)
        except Exception:
            pass
    try:
        return _render_plain(**kwargs)
    except Exception:
        return None


# ── Renderers ─────────────────────────────────────────────────────────────────

def _render_tiled(o_lat, o_lon, d_lat, d_lon, origin_icao, dest_icao,
                  airspaces, cruise_alt_ft, width_in, height_in, dark):
    """Renderer that adds a real tile basemap via contextily."""
    import contextily as ctx  # re-import here to satisfy linters

    lon_min, lon_max, lat_min, lat_max = _compute_bounds(
        o_lon, o_lat, d_lon, d_lat, airspaces
    )

    fig, ax = plt.subplots(figsize=(width_in, height_in))
    fig.patch.set_facecolor("#0f172a" if dark else "white")
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect("auto")

    # Tile basemap — added first so overlays render on top
    source = (ctx.providers.CartoDB.DarkMatter
               if dark else ctx.providers.CartoDB.Positron)
    ctx.add_basemap(ax, crs="EPSG:4326", source=source,
                    reset_extent=False, attribution=False)

    # Restore limits (contextily can shift them)
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    _draw_overlays(ax, o_lat, o_lon, d_lat, d_lon,
                   origin_icao, dest_icao,
                   airspaces, cruise_alt_ft, dark,
                   lon_min, lon_max, lat_min, lat_max)
    _style_axes(ax, dark)
    return _export(fig, dark)


def _render_plain(o_lat, o_lon, d_lat, d_lon, origin_icao, dest_icao,
                  airspaces, cruise_alt_ft, width_in, height_in, dark):
    """Fallback renderer — colored background, no network tile fetching."""
    lon_min, lon_max, lat_min, lat_max = _compute_bounds(
        o_lon, o_lat, d_lon, d_lat, airspaces
    )

    fig, ax = plt.subplots(figsize=(width_in, height_in))
    fig.patch.set_facecolor("#0f172a" if dark else "white")
    ax.set_facecolor("#1e293b" if dark else "#deeeff")
    ax.grid(True, color=("#334155" if dark else "white"),
            linewidth=0.4, alpha=0.55, linestyle=":")
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect("auto")

    _draw_overlays(ax, o_lat, o_lon, d_lat, d_lon,
                   origin_icao, dest_icao,
                   airspaces, cruise_alt_ft, dark,
                   lon_min, lon_max, lat_min, lat_max)
    _style_axes(ax, dark)
    return _export(fig, dark)


# ── Shared drawing ─────────────────────────────────────────────────────────────

def _draw_overlays(ax, o_lat, o_lon, d_lat, d_lon,
                   origin_icao, dest_icao,
                   airspaces, cruise_alt_ft, dark,
                   lon_min, lon_max, lat_min, lat_max):
    """Draw airspace polygons, route arrow, airport markers, labels."""
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min

    # ── Airspace polygons ─────────────────────────────────────────────────────
    legend_classes = set()
    if airspaces:
        for asp in airspaces:
            cls     = asp.get("airspace_class", "?")
            polygon = asp.get("polygon")
            if cls not in _CLS_COLOR or not polygon or polygon.is_empty:
                continue
            color = _CLS_COLOR[cls]
            try:
                xs, ys = polygon.exterior.xy
            except Exception:
                continue
            # Discard polygons entirely outside our view
            if max(xs) < lon_min or min(xs) > lon_max:
                continue
            if max(ys) < lat_min or min(ys) > lat_max:
                continue

            ax.fill(xs, ys, alpha=0.18, color=color, zorder=2)
            ax.plot(xs, ys, color=color, linewidth=0.9, alpha=0.70, zorder=2)
            legend_classes.add(cls)

            # Label near centroid for B/C/D only
            if cls in ("B", "C", "D"):
                cx, cy = float(polygon.centroid.x), float(polygon.centroid.y)
                if lon_min < cx < lon_max and lat_min < cy < lat_max:
                    lower = asp.get("lower_ft", "SFC")
                    upper = asp.get("upper_ft", "?")
                    ax.text(
                        cx, cy,
                        f"Cls {cls}\n{lower}–{upper}",
                        fontsize=5.5, color=color,
                        ha="center", va="center", zorder=3, alpha=0.95,
                        bbox=dict(
                            boxstyle="round,pad=0.2",
                            fc=("#0f172a" if dark else "white"),
                            ec=color, alpha=0.80, lw=0.6,
                        ),
                    )

    # ── Route arrow ───────────────────────────────────────────────────────────
    ax.annotate(
        "",
        xy=(d_lon, d_lat), xytext=(o_lon, o_lat),
        arrowprops=dict(
            arrowstyle="-|>", color=_ROUTE_COLOR,
            lw=2.2, mutation_scale=14,
        ),
        zorder=5,
    )
    ax.plot([o_lon, d_lon], [o_lat, d_lat],
            color=_ROUTE_COLOR, lw=1.6, alpha=0.75, zorder=4)

    # Distance + bearing mid-label
    dist = _haversine_nm(o_lat, o_lon, d_lat, d_lon)
    hdg  = _bearing(o_lat, o_lon, d_lat, d_lon)
    mx   = (o_lon + d_lon) / 2
    my   = (o_lat + d_lat) / 2 + lat_range * 0.025
    ax.text(
        mx, my,
        f"  {dist:.0f} nm  ·  {hdg:.0f}°T  ",
        color=_ROUTE_COLOR, fontsize=7.5, ha="center", va="bottom",
        fontweight="bold", zorder=6,
        bbox=dict(
            boxstyle="round,pad=0.25",
            fc=("#0f172a" if dark else "white"),
            ec=_ROUTE_COLOR, alpha=0.90, lw=0.8,
        ),
    )

    # ── Airport markers ───────────────────────────────────────────────────────
    ax.scatter([o_lon], [o_lat], s=160, c="#22c55e",
               zorder=7, marker="*", edgecolors="white", linewidths=0.4)
    ax.scatter([d_lon], [d_lat], s=160, c="#ef4444",
               zorder=7, marker="*", edgecolors="white", linewidths=0.4)

    off = lon_range * 0.028
    tc  = "white" if dark else "#1e293b"
    for lon, lat, label in [
        (o_lon, o_lat, origin_icao),
        (d_lon, d_lat, dest_icao),
    ]:
        ha  = "left"  if lon <= (o_lon + d_lon) / 2 else "right"
        xo  = off     if ha == "left"                else -off
        ax.annotate(
            label, (lon, lat),
            xytext=(lon + xo, lat + lat_range * 0.025),
            color=tc, fontsize=9, fontweight="bold",
            ha=ha, va="bottom", zorder=8,
        )

    # Cruise altitude watermark
    ax.text(
        0.01, 0.02, f"Cruise {cruise_alt_ft:,} ft MSL",
        transform=ax.transAxes,
        color=("#94a3b8" if dark else "#6b7280"),
        fontsize=6.5, va="bottom",
    )

    # ── Legend ────────────────────────────────────────────────────────────────
    handles = [
        mpatches.Patch(fc=_CLS_COLOR[c], ec=_CLS_COLOR[c],
                       alpha=0.65, label=_CLS_LABEL.get(c, f"Class {c}"))
        for c in sorted(legend_classes) if c in _CLS_COLOR
    ]
    handles.append(
        mpatches.Patch(fc=_ROUTE_COLOR, ec=_ROUTE_COLOR,
                       alpha=0.85, label="Direct Route")
    )
    if handles:
        ax.legend(
            handles=handles, loc="upper right", fontsize=6.5,
            facecolor=("#1e293b" if dark else "white"),
            edgecolor=("#334155" if dark else "#e2e8f0"),
            labelcolor=("white" if dark else "#1e293b"),
            framealpha=0.92,
        )


# ── Layout helpers ─────────────────────────────────────────────────────────────

def _compute_bounds(o_lon, o_lat, d_lon, d_lat, airspaces):
    """Map extent in (lon_min, lon_max, lat_min, lat_max) with padding."""
    lon_span = max(abs(d_lon - o_lon), 0.20)
    lat_span = max(abs(d_lat - o_lat), 0.15)
    pad_lon  = max(lon_span * 0.45, 0.15)
    pad_lat  = max(lat_span * 0.50, 0.12)
    return (
        min(o_lon, d_lon) - pad_lon, max(o_lon, d_lon) + pad_lon,
        min(o_lat, d_lat) - pad_lat, max(o_lat, d_lat) + pad_lat,
    )


def _style_axes(ax, dark):
    tc = "#94a3b8" if dark else "#475569"
    ax.tick_params(colors=tc, labelsize=6.5)
    for spine in ax.spines.values():
        spine.set_color("#334155" if dark else "#e2e8f0")
    ax.set_xlabel("Longitude", color=tc, fontsize=7)
    ax.set_ylabel("Latitude",  color=tc, fontsize=7)


def _export(fig, dark):
    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format="png",
                facecolor=("#0f172a" if dark else "white"),
                dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ── Geometry ──────────────────────────────────────────────────────────────────

def _haversine_nm(lat1, lon1, lat2, lon2):
    R  = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = (math.sin(dp / 2) ** 2
          + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _bearing(lat1, lon1, lat2, lon2):
    la1, lo1 = math.radians(lat1), math.radians(lon1)
    la2, lo2 = math.radians(lat2), math.radians(lon2)
    dlo = lo2 - lo1
    x   = math.sin(dlo) * math.cos(la2)
    y   = (math.cos(la1) * math.sin(la2)
           - math.sin(la1) * math.cos(la2) * math.cos(dlo))
    return (math.degrees(math.atan2(x, y)) + 360) % 360
