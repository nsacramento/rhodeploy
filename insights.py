"""
Rho — pre-flight insights engine
Aggregates weather, airspace, and airport data into an actionable pilot brief.

Go/no-go thresholds (VFR student pilot defaults):
  VFR:   ceiling >= 3,000 ft AGL  AND  visibility >= 5 sm
  MVFR:  ceiling 1,000–2,999 ft  OR   visibility 3–4 sm  (caution)
  No-go: ceiling < 1,000 ft       OR   visibility < 3 sm
"""

import math
from rho.modules.weather import get_weather_brief, get_winds_aloft_for_state
from rho.modules.airport import get_airport_full
from rho.modules.routing import get_airspace_near, generate_routes

# ── Thresholds ────────────────────────────────────────────────────────────────
MAX_WIND_KT = 15    # student pilot comfort threshold
MAX_XWIND_KT = 10   # crosswind caution threshold


def get_preflight_brief(origin_icao, dest_icao, cruise_alt_ft=3500):
    """
    Full pre-flight brief for a VFR cross-country.

    Returns a dict with:
        origin_icao, dest_icao, cruise_alt_ft,
        origin_wx, dest_wx, origin_apt, dest_apt,
        origin_assess, dest_assess,
        route, hazards,
        recommendation,   "GO" | "CAUTION" | "NO-GO"
        reason,
        summary
    """
    origin_icao = origin_icao.upper()
    dest_icao   = dest_icao.upper()

    # ── Fetch data ────────────────────────────────────────────────────────────
    origin_wx = get_weather_brief(origin_icao)
    dest_wx   = get_weather_brief(dest_icao)

    try:
        origin_apt = get_airport_full(origin_icao)
    except Exception:
        origin_apt = None

    try:
        dest_apt = get_airport_full(dest_icao)
    except Exception:
        dest_apt = None

    # ── Winds aloft ───────────────────────────────────────────────────────────
    winds_aloft = None
    origin_state = (origin_apt.get("state") or "") if origin_apt else ""
    if origin_state:
        try:
            winds_aloft = get_winds_aloft_for_state(origin_state)
        except Exception:
            winds_aloft = None

    # ── Routing ───────────────────────────────────────────────────────────────
    route = None
    airspaces = None
    airspace_warnings = []
    if origin_apt and dest_apt:
        o_lat = origin_apt.get("lat")
        o_lon = origin_apt.get("lon")
        d_lat = dest_apt.get("lat")
        d_lon = dest_apt.get("lon")
        if all(v is not None for v in [o_lat, o_lon, d_lat, d_lon]):
            # Expand radius to 60 nm so destination airspace is reliably included
            airspaces = get_airspace_near(o_lat, o_lon, radius_nm=60)
            route = generate_routes(o_lat, o_lon, d_lat, d_lon, airspaces,
                                    cruise_alt_ft=cruise_alt_ft)
            for p in route["direct"].get("airspace_penetrations", []):
                airspace_warnings.append(
                    f"Route penetrates Class {p['class']}: {p['name']} ({p['lower']}–{p['upper']})"
                )

    # ── Weather assessments ───────────────────────────────────────────────────
    origin_assess = _assess_wx(origin_wx, origin_apt)
    dest_assess   = _assess_wx(dest_wx,   dest_apt)

    # ── Hazard list ───────────────────────────────────────────────────────────
    # Grab origin coords for geo-filtering national wx products
    o_lat_ref = origin_apt.get("lat") if origin_apt else None
    o_lon_ref = origin_apt.get("lon") if origin_apt else None
    d_lat_ref = dest_apt.get("lat")   if dest_apt   else None
    d_lon_ref = dest_apt.get("lon")   if dest_apt   else None

    hazards = list(origin_assess["warnings"])
    hazards += [f"[{dest_icao}] {w}" for w in dest_assess["warnings"]]
    hazards += airspace_warnings

    # SIGMETs — filter to those whose area overlaps the route region
    active_sigmets = []
    for s in (origin_wx.get("sigmets") or []):
        if _near_route(s.get("area_coords") or [], o_lat_ref, o_lon_ref, d_lat_ref, d_lon_ref):
            active_sigmets.append(s)
            hazards.append(f"SIGMET active: {s.get('hazard')} — see SIGMET section below")

    # G-AIRMETs — same geo filter, only flag meaningful hazards
    for g in (origin_wx.get("gairmets") or []):
        if g.get("hazard") in ("ICE", "TURB", "IFR"):
            if _near_route(g.get("area_coords") or [], o_lat_ref, o_lon_ref, d_lat_ref, d_lon_ref):
                hazards.append(
                    f"G-AIRMET {(g.get('product') or '').upper()}: "
                    f"{g.get('hazard')} due to {g.get('due_to') or 'unknown'}"
                )

    # ── Go/no-go ──────────────────────────────────────────────────────────────
    recommendation, reason = _go_nogo(origin_assess, dest_assess)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _build_summary(
        origin_icao, dest_icao,
        origin_assess, dest_assess,
        route, recommendation, reason, hazards
    )

    return {
        "origin_icao":    origin_icao,
        "dest_icao":      dest_icao,
        "cruise_alt_ft":  cruise_alt_ft,
        "origin_wx":      origin_wx,
        "dest_wx":        dest_wx,
        "origin_apt":     origin_apt,
        "dest_apt":       dest_apt,
        "origin_assess":  origin_assess,
        "dest_assess":    dest_assess,
        "route":          route,
        "airspaces":      airspaces,   # full list for route map rendering
        "winds_aloft":    winds_aloft, # { "3000": {dir, spd, temp_c, label}, ... }
        "hazards":        hazards,
        "sigmets":        active_sigmets,
        "recommendation": recommendation,
        "reason":         reason,
        "summary":        summary,
    }


# ── Weather assessment ────────────────────────────────────────────────────────

def _assess_wx(wx_brief, apt=None):
    """
    Assess a weather brief dict. Returns a dict with:
        category, ceiling_ft, visibility, wind_kt, wind_dir,
        crosswind_kt, best_runway, warnings, trend, raw_metar
    """
    metar      = wx_brief.get("metar") or {}
    category   = metar.get("flight_category")
    ceiling_ft = _ceiling_from_clouds(metar.get("clouds") or [])
    visibility = _parse_vis(metar.get("visibility"))
    wind_kt    = metar.get("wind_kt") or 0
    wind_dir   = metar.get("wind_dir")

    if not category:
        category = _derive_category(ceiling_ft, visibility)

    # Best runway crosswind
    crosswind_kt = None
    best_runway  = None
    if apt and wind_dir is not None and wind_kt:
        crosswind_kt, best_runway = _best_runway_crosswind(
            apt.get("runways") or [], wind_dir, wind_kt
        )

    warnings = []
    if category in ("IFR", "LIFR"):
        warnings.append(f"Flight category {category} — below VFR minimums")
    elif category == "MVFR":
        warnings.append("MVFR — marginal conditions, monitor closely")

    if wind_kt > MAX_WIND_KT:
        warnings.append(f"Surface winds {wind_kt} kt (student threshold {MAX_WIND_KT} kt)")

    if crosswind_kt is not None and crosswind_kt > MAX_XWIND_KT:
        warnings.append(
            f"Crosswind ~{crosswind_kt:.0f} kt on best runway ({best_runway})"
        )

    trend = _taf_trend(wx_brief.get("taf"))
    if trend == "deteriorating":
        warnings.append("TAF trend: conditions deteriorating")

    return {
        "category":      category or "UNKNOWN",
        "ceiling_ft":    ceiling_ft,
        "visibility":    visibility,
        "wind_kt":       wind_kt,
        "wind_dir":      wind_dir,
        "crosswind_kt":  crosswind_kt,
        "best_runway":   best_runway,
        "warnings":      warnings,
        "trend":         trend,
        "raw_metar":     metar.get("raw"),
        # ATIS-style fields
        "temp_c":        metar.get("temp_c"),
        "dewpoint_c":    metar.get("dewpoint_c"),
        "altimeter":     metar.get("altimeter"),
        "sky_conditions": _format_sky(metar.get("clouds") or []),
        "clouds":        metar.get("clouds") or [],
    }


def _format_sky(clouds):
    """Format cloud layers into METAR-style sky condition string, e.g. 'FEW018 BKN065'."""
    if not clouds:
        return "CLR"
    parts = []
    for layer in clouds:
        cover = (layer.get("cover") or "").strip()
        base  = layer.get("base")
        if cover and base is not None:
            parts.append(f"{cover}{int(base / 100):03d}")
        elif cover:
            parts.append(cover)
    return " ".join(parts) if parts else "CLR"


def _ceiling_from_clouds(clouds):
    """Return lowest BKN or OVC ceiling in feet AGL, or None if clear."""
    ceiling = None
    for layer in clouds:
        cover = layer.get("cover") or ""
        if cover in ("BKN", "OVC"):
            base = layer.get("base")
            if base is not None:
                ft = int(base)   # aviationweather.gov returns base already in feet AGL
                if ceiling is None or ft < ceiling:
                    ceiling = ft
    return ceiling


def _parse_vis(vis):
    """Parse visibility value — may be string '10+' or numeric."""
    if vis is None:
        return None
    try:
        return float(str(vis).replace("+", ""))
    except ValueError:
        return None


def _derive_category(ceiling_ft, visibility_sm):
    """Derive VFR/MVFR/IFR/LIFR from ceiling and visibility."""
    rank = []
    if ceiling_ft is not None:
        if ceiling_ft < 500:    rank.append("LIFR")
        elif ceiling_ft < 1000: rank.append("IFR")
        elif ceiling_ft < 3000: rank.append("MVFR")
        else:                   rank.append("VFR")
    if visibility_sm is not None:
        if visibility_sm < 1:   rank.append("LIFR")
        elif visibility_sm < 3: rank.append("IFR")
        elif visibility_sm < 5: rank.append("MVFR")
        else:                   rank.append("VFR")
    if not rank:
        return "VFR"   # assume clear if no data
    order = ["LIFR", "IFR", "MVFR", "VFR"]
    return min(rank, key=lambda c: order.index(c) if c in order else 99)


def _taf_trend(taf):
    """Return 'improving', 'deteriorating', 'steady', or None."""
    if not taf:
        return None
    forecasts = taf.get("forecasts") or []
    rank = {"VFR": 0, "MVFR": 1, "IFR": 2, "LIFR": 3}
    scores = []
    for f in forecasts:
        c = _derive_category(
            _ceiling_from_clouds(f.get("clouds") or []),
            _parse_vis(f.get("visibility"))
        )
        scores.append(rank.get(c, 0))
    if len(scores) < 2:
        return "steady"
    if scores[-1] > scores[0]:
        return "deteriorating"
    if scores[-1] < scores[0]:
        return "improving"
    return "steady"


def _best_runway_crosswind(runways, wind_dir, wind_kt):
    """
    Return (crosswind_kt, designator) for the runway with smallest crosswind.
    Designator format from FAA: '14/32', '14L/32R', etc.
    """
    best_xw  = None
    best_rwy = None
    for rwy in runways:
        desig   = rwy.get("designator") or ""
        primary = desig.split("/")[0].strip()
        num     = "".join(c for c in primary if c.isdigit())
        if not num:
            continue
        rwy_hdg = int(num) * 10
        angle   = abs(wind_dir - rwy_hdg)
        if angle > 180:
            angle = 360 - angle
        xw = abs(wind_kt * math.sin(math.radians(angle)))
        if best_xw is None or xw < best_xw:
            best_xw  = xw
            best_rwy = desig
    return (round(best_xw, 1) if best_xw is not None else None, best_rwy)


def _near_route(area_coords, lat1, lon1, lat2, lon2, pad_deg=2.5):
    """
    Return True if any coord in area_coords falls within pad_deg of the
    route bounding box. Filters out national wx products not near the flight.
    Returns True if coords are unavailable (fail open — don't silently drop).
    """
    if not area_coords:
        return True   # no coords to check — include by default
    if any(v is None for v in [lat1, lon1, lat2, lon2]):
        return True   # no route reference — include by default
    min_lat = min(lat1, lat2) - pad_deg
    max_lat = max(lat1, lat2) + pad_deg
    min_lon = min(lon1, lon2) - pad_deg
    max_lon = max(lon1, lon2) + pad_deg
    for coord in area_coords:
        c_lat = coord.get("lat")
        c_lon = coord.get("lon")
        try:
            c_lat = float(c_lat)
            c_lon = float(c_lon)
        except (TypeError, ValueError):
            continue
        if min_lat <= c_lat <= max_lat and min_lon <= c_lon <= max_lon:
                return True
    return False


# ── Go/no-go ──────────────────────────────────────────────────────────────────

def _go_nogo(origin_assess, dest_assess):
    """Return (recommendation, reason) string pair."""
    no_go   = {"IFR", "LIFR"}
    caution = {"MVFR"}

    if origin_assess["category"] in no_go:
        return "NO-GO", f"Origin is {origin_assess['category']} — below VFR minimums"
    if dest_assess["category"] in no_go:
        return "NO-GO", f"Destination is {dest_assess['category']} — below VFR minimums"

    reasons = []
    if origin_assess["category"] in caution:
        reasons.append("origin MVFR")
    if dest_assess["category"] in caution:
        reasons.append("destination MVFR")
    if origin_assess.get("trend") == "deteriorating":
        reasons.append("origin weather deteriorating per TAF")
    if dest_assess.get("trend") == "deteriorating":
        reasons.append("destination weather deteriorating per TAF")
    if origin_assess["wind_kt"] > MAX_WIND_KT:
        reasons.append(f"winds {origin_assess['wind_kt']} kt at origin exceed student threshold")

    if reasons:
        return "CAUTION", "; ".join(reasons)
    return "GO", "VFR conditions at both airports, no significant hazards"


# ── Summary ───────────────────────────────────────────────────────────────────

def _build_summary(origin, dest, o_wx, d_wx, route, rec, reason, hazards):
    """Build a plain-English one-paragraph pre-flight brief."""
    dist_str = f" ({route['direct']['distance_nm']} nm)" if route else ""

    wind_str = "winds unknown"
    if o_wx["wind_dir"] and o_wx["wind_kt"]:
        wind_str = f"{o_wx['wind_dir']}° at {o_wx['wind_kt']} kt"

    ceiling_str = f", ceiling {o_wx['ceiling_ft']:,} ft AGL" if o_wx["ceiling_ft"] else ""
    vis_str     = f", vis {o_wx['visibility']} sm" if o_wx["visibility"] else ""
    trend_str   = (
        f" TAF trend: {o_wx['trend']}."
        if o_wx.get("trend") and o_wx["trend"] != "steady"
        else ""
    )

    hazard_str = ""
    if hazards:
        shown = hazards[:3]
        more  = f" (+{len(hazards) - 3} more)" if len(hazards) > 3 else ""
        hazard_str = f" Active hazards: {'; '.join(shown)}{more}."

    return (
        f"{origin}→{dest}{dist_str}: "
        f"{origin} is {o_wx['category']} ({wind_str}{ceiling_str}{vis_str}).{trend_str} "
        f"{dest} is {d_wx['category']}.{hazard_str} "
        f"Recommendation: {rec} — {reason}."
    )
