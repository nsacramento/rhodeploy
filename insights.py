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
from rho.modules.tfr import get_tfrs_near_route

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
            winds_aloft = get_winds_aloft_for_state(
                origin_state, lat=origin_apt.get("lat"), lon=origin_apt.get("lon"))
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

    # TFRs — fetch active TFRs along the route corridor (30 nm pad)
    active_tfrs = []
    if all(v is not None for v in [o_lat_ref, o_lon_ref, d_lat_ref, d_lon_ref]):
        try:
            active_tfrs = get_tfrs_near_route(
                o_lat_ref, o_lon_ref,
                d_lat_ref, d_lon_ref,
                flight_rules="VFR",
                pad_nm=30,
            )
        except Exception:
            active_tfrs = []
    for tfr in active_tfrs:
        hazards.append(
            f"TFR {tfr['notam_id']} within 30 nm of route — "
            f"{tfr['tfr_type']}, SFC–{tfr['alt_ceil']}, radius {tfr['radius_nm']:.0f} nm"
        )

    # ── Go/no-go ──────────────────────────────────────────────────────────────
    # ── VFR weather minimums by airspace (91.155) ─────────────────────────────
    vfr_factors, vfr_mins = [], None
    try:
        from rho.modules.airspace_mins import check_vfr_minimums
        from rho.modules.comms import get_comms
        _partial = {
            "origin_icao": origin_icao, "dest_icao": dest_icao, "cruise_alt_ft": cruise_alt_ft,
            "origin_apt": origin_apt, "dest_apt": dest_apt,
            "origin_assess": origin_assess, "dest_assess": dest_assess,
            "airspaces": airspaces, "route": route,
        }
        vfr_factors, _rows, _hl = check_vfr_minimums(
            _partial, get_comms(origin_icao), get_comms(dest_icao))
        vfr_mins = {"rows": _rows, "highlight": sorted(_hl)}
    except Exception:
        vfr_factors, vfr_mins = [], None

    recommendation, reason, factors = _go_nogo(
        origin_assess, dest_assess, origin_icao, dest_icao,
        sigmets=active_sigmets, tfrs=active_tfrs, extra_factors=vfr_factors,
    )

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
        "tfrs":           active_tfrs,
        "recommendation": recommendation,
        "reason":         reason,
        "factors":        factors,
        "vfr_mins":       vfr_mins,    # {rows, highlight} — today's weather vs 91.155 minimums     # [{level, type, airport, short, detail}] — why GO/CAUTION/NO-GO
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

    # Best runway crosswind (run even with calm winds so runway always shows)
    crosswind_kt = None
    best_runway  = None
    if apt and wind_dir is not None:
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
        "wind_gust_kt":  metar.get("wind_gust_kt"),
        "wx_string":     metar.get("wx_string") or "",
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

_LEVEL_RANK = {"NO-GO": 2, "CAUTION": 1, "NOTE": 0}

_COVER_WORD = {"BKN": "broken", "OVC": "overcast", "VV": "vertical visibility"}


def _ceiling_cover(clouds, ceiling_ft):
    for layer in clouds or []:
        if layer.get("cover") in ("BKN", "OVC", "VV") and layer.get("base") == ceiling_ft:
            return _COVER_WORD.get(layer.get("cover"), "")
    return ""


def _wx_factors(wx_string):
    """Present-weather codes from the METAR -> list of (level, type, short, detail)."""
    out = []
    w = (wx_string or "").upper()
    if not w:
        return out
    toks = w.split()
    if any("TS" in t and not t.startswith("VC") for t in toks):
        out.append(("NO-GO", "Thunderstorm", "thunderstorm at the field",
                    f"METAR reports a thunderstorm ({w}). Never fly into or near a thunderstorm — "
                    "stay 20 nm away."))
    elif "VCTS" in toks:
        out.append(("CAUTION", "Thunderstorm", "thunderstorms nearby",
                    f"Thunderstorm in the vicinity (within 10 sm) — {w}. Expect gusts, rain, "
                    "and rapidly changing conditions."))
    if any(t.lstrip("+-").startswith("FZ") and t.lstrip("+-") != "FZFG" for t in toks) \
            or any(x in w for x in ("PL", "GR", "GS", "SN")):
        out.append(("NO-GO", "Icing / frozen precip", "freezing or frozen precipitation",
                    f"METAR reports {w}. Training aircraft are not certified for known icing."))
    if any(t.startswith("+") and ("RA" in t or "SH" in t) for t in toks):
        out.append(("CAUTION", "Heavy rain", "heavy rain",
                    f"Heavy precipitation ({w}) — visibility can drop quickly."))
    elif any(("RA" in t or "DZ" in t) and "TS" not in t for t in toks):
        out.append(("NOTE", "Rain", "light/moderate rain",
                    f"Precipitation reported ({w}). Watch visibility and cloud bases."))
    if any(t in ("FG", "FZFG", "MIFG", "BCFG", "PRFG") for t in toks):
        out.append(("CAUTION", "Fog", "fog",
                    f"Fog reported ({w}). Fog can close an airport in minutes."))
    elif any(t in ("BR", "HZ", "FU") for t in toks):
        out.append(("NOTE", "Mist / haze", "mist or haze",
                    f"{w} reported — expect reduced slant-range visibility."))
    return out


def _go_nogo(origin_assess, dest_assess, origin_icao="Origin", dest_icao="Destination",
             sigmets=None, tfrs=None, extra_factors=None):
    """
    Return (recommendation, reason, factors).

    factors: list of dicts, worst first:
        {level: "NO-GO"|"CAUTION"|"NOTE", type, airport, short, detail}
    NOTE items are informational and never change the recommendation.
    """
    factors = []

    def add(level, ftype, airport, short, detail):
        factors.append({"level": level, "type": ftype, "airport": airport,
                        "short": short, "detail": detail})

    for icao, a in ((origin_icao, origin_assess), (dest_icao, dest_assess)):
        cat     = a.get("category") or "UNKNOWN"
        ceil    = a.get("ceiling_ft")
        vis     = a.get("visibility")
        wind    = a.get("wind_kt") or 0
        gust    = a.get("wind_gust_kt")
        xw      = a.get("crosswind_kt")
        cover   = _ceiling_cover(a.get("clouds"), ceil)
        cover_s = f" ({cover})" if cover else ""

        # ── Flight category: say which element drives it ────────────────────
        if not a.get("raw_metar"):
            add("CAUTION", "No weather", icao, "no current METAR",
                "No current observation, so conditions here are unknown — get weather from a nearby "
                "airport or an official briefing before going.")
        if cat in ("IFR", "LIFR", "MVFR"):
            level = "NO-GO" if cat in ("IFR", "LIFR") else "CAUTION"
            found = False
            if ceil is not None and ceil < 3000:
                if ceil < 1000:
                    rule = "below 1,000 ft is IFR"
                else:
                    rule = "1,000–3,000 ft is MVFR; VFR needs 3,000+"
                layer = (cover.capitalize() if cover else "Ceiling") + " layer"
                add(level, "Low ceiling", icao, f"ceiling {ceil:,} ft{cover_s} — {cat}",
                    f"{layer} at {ceil:,} ft AGL. Ceiling {rule}.")
                found = True
            if vis is not None and vis < 5:
                rule = "below 3 sm is IFR" if vis < 3 else "3–5 sm is MVFR; VFR needs 5+"
                add(level, "Low visibility", icao, f"visibility {vis:g} sm — {cat}",
                    f"Visibility {vis:g} statute miles. Visibility {rule}.")
                found = True
            if not found:
                add(level, "Flight category", icao, f"reported {cat}",
                    f"Station reports {cat}. Check the raw METAR for the limiting element.")

        # ── Wind ─────────────────────────────────────────────────────────────
        if wind > MAX_WIND_KT:
            add("CAUTION", "Strong wind", icao, f"wind {wind} kt",
                f"Surface wind {wind} kt exceeds the {MAX_WIND_KT} kt student comfort limit.")
        if gust and (gust > MAX_WIND_KT or gust - wind >= 10):
            add("CAUTION", "Gusts", icao, f"gusting {gust} kt",
                f"Wind {wind} gusting {gust} kt. Add half the gust factor to approach speed; "
                "expect a bumpy, workload-heavy landing.")
        if xw is not None and xw > MAX_XWIND_KT:
            add("CAUTION", "Crosswind", icao, f"crosswind ~{xw:.0f} kt",
                f"~{xw:.0f} kt crosswind on the best runway ({a.get('best_runway')}) — above the "
                f"{MAX_XWIND_KT} kt student threshold. Check your aircraft's demonstrated crosswind.")

        # ── Present weather ───────────────────────────────────────────────────
        for level, ftype, short, detail in _wx_factors(a.get("wx_string")):
            add(level, ftype, icao, short, detail)

        # ── Forecast trend ────────────────────────────────────────────────────
        if a.get("trend") == "deteriorating":
            add("CAUTION", "Forecast worsening", icao, "TAF worsening",
                "The TAF shows conditions getting worse later in the period — check timing "
                "against your departure and return.")

        # ── Temp/dewpoint spread (fog / low cloud risk) ──────────────────────
        tc, dc = a.get("temp_c"), a.get("dewpoint_c")
        if tc is not None and dc is not None and (tc - dc) <= 2.0:
            add("NOTE", "Fog risk", icao, f"temp/dew spread {round(tc - dc, 1)}°C",
                f"Temperature and dewpoint are within {round(tc - dc, 1)}°C — air is nearly "
                "saturated. Clouds and visibility can lower quickly, especially near sunrise/sunset.")

    # ── Route-wide products ───────────────────────────────────────────────────
    for sg in sigmets or []:
        add("CAUTION", "SIGMET", "Route", f"SIGMET: {sg.get('hazard') or 'active'}",
            f"SIGMET for {sg.get('hazard') or 'hazardous weather'} near the route — read the full text below.")
    for t in tfrs or []:
        add("NOTE", "TFR", "Route", f"TFR {t.get('notam_id', '')}".strip(),
            "Temporary flight restriction within 30 nm of the route — check the NOTAM before flight.")

    factors.extend(extra_factors or [])
    factors.sort(key=lambda f: -_LEVEL_RANK[f["level"]])
    worst = factors[0]["level"] if factors else "NOTE"
    if worst == "NOTE":
        return ("GO",
                "VFR at both airports, winds within student limits, no thunderstorms or SIGMETs near the route",
                factors)

    top = [f for f in factors if f["level"] == worst]
    parts = [f"{f['airport']} {f['short']}" if f["airport"] != "Route" else f["short"]
             for f in top[:3]]
    more = f" (+{len(top) - 3} more)" if len(top) > 3 else ""
    return worst, "; ".join(parts) + more, factors


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
