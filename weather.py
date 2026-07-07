"""
Rho — weather module
Fetches METARs, TAFs, PIREPs, SIGMETs, and G-AIRMETs from aviationweather.gov.

All endpoints are free, no API key required.
Base URL: https://aviationweather.gov/api/data/

Note: CONUS text AIRMETs were discontinued January 2025. G-AIRMETs replace them.
"""

import time
import requests
from datetime import datetime, timezone

_BASE = "https://aviationweather.gov/api/data"
_HEADERS = {"User-Agent": "Rho/1.0 student-pilot-copilot"}
_TIMEOUT = 20
_RETRIES = 2


def _get(endpoint, params):
    """Make a GET request with retry on timeout; returns parsed JSON or None."""
    url = f"{_BASE}/{endpoint}"
    full_params = {**params, "format": "json"}
    last_err = None
    for attempt in range(_RETRIES):
        try:
            resp = requests.get(
                url,
                params=full_params,
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as e:
            last_err = e
            if attempt < _RETRIES - 1:
                time.sleep(1)
        except requests.exceptions.RequestException:
            raise
    raise last_err


def _hpa_to_inhg(hpa):
    """Convert hectopascals to inches of mercury. API returns altim in hPa."""
    if hpa is None:
        return None
    try:
        return round(float(hpa) / 33.8639, 2)
    except (ValueError, TypeError):
        return None


# ── METAR ────────────────────────────────────────────────────────────────────

def get_metar(icao):
    """
    Fetch the latest METAR for a given ICAO identifier.

    Returns a dict with keys:
        icao, raw, temp_c, dewpoint_c, wind_dir, wind_kt,
        visibility, altimeter, flight_category, clouds, observed_utc
    Returns None if no METAR is available.
    """
    data = _get("metar", {"ids": icao.upper(), "mostRecent": "true"})
    if not data:
        return None

    m = data[0]
    return {
        "icao": m.get("icaoId"),
        "raw": m.get("rawOb"),
        "temp_c": m.get("temp"),
        "dewpoint_c": m.get("dewp"),
        "wind_dir": m.get("wdir"),
        "wind_kt": m.get("wspd"),
        "visibility": m.get("visib"),
        "altimeter": _hpa_to_inhg(m.get("altim")),
        "flight_category": m.get("fltCat"),
        "clouds": m.get("clouds", []),
        "observed_utc": _epoch_to_iso(m.get("obsTime")),
    }


# ── TAF ──────────────────────────────────────────────────────────────────────

def get_taf(icao):
    """
    Fetch the latest TAF for a given ICAO identifier.

    Returns a dict with keys:
        icao, raw, issued_utc, valid_from_utc, valid_to_utc, forecasts
    Each forecast period in 'forecasts' contains:
        change_type, valid_from_utc, valid_to_utc, wind_dir, wind_kt,
        visibility, clouds
    Returns None if no TAF is available.
    """
    data = _get("taf", {"ids": icao.upper(), "mostRecent": "true"})
    if not data:
        return None

    t = data[0]
    forecasts = []
    for f in t.get("fcsts", []):
        forecasts.append({
            "change_type": f.get("fcstChange"),
            "valid_from_utc": _epoch_to_iso(f.get("timeFrom")),
            "valid_to_utc": _epoch_to_iso(f.get("timeTo")),
            "wind_dir": f.get("wdir"),
            "wind_kt": f.get("wspd"),
            "wind_gust_kt": f.get("wgst"),
            "visibility": f.get("visib"),
            "wx_string": f.get("wxString"),
            "clouds": f.get("clouds", []),
        })

    return {
        "icao": t.get("icaoId"),
        "raw": t.get("rawTAF"),
        "issued_utc": t.get("issueTime"),
        "valid_from_utc": _epoch_to_iso(t.get("validTimeFrom")),
        "valid_to_utc": _epoch_to_iso(t.get("validTimeTo")),
        "forecasts": forecasts,
    }


# ── PIREPs ───────────────────────────────────────────────────────────────────

def get_pireps(icao, distance_nm=100):
    """
    Fetch recent PIREPs within distance_nm nautical miles of a given airport.

    Returns a list of dicts, each with keys:
        raw, aircraft_type, altitude_ft, sky_cover,
        turbulence, icing, reported_utc, lat, lon
    Returns empty list if none available.
    """
    data = _get("pirep", {"id": icao.upper(), "distance": distance_nm})
    if not data:
        return []

    pireps = []
    for p in data:
        pireps.append({
            "raw": p.get("rawOb"),
            "aircraft_type": p.get("acType"),
            "altitude_ft": p.get("altitude"),
            "sky_cover": p.get("skyCondition"),
            "turbulence": p.get("turbulenceType"),
            "icing": p.get("icingType"),
            "reported_utc": p.get("obsTime"),
            "lat": p.get("lat"),
            "lon": p.get("lon"),
        })

    return pireps


# ── SIGMETs ──────────────────────────────────────────────────────────────────

def get_sigmets():
    """
    Fetch all active domestic SIGMETs.

    Returns a list of dicts, each with keys:
        hazard, raw, valid_from_utc, valid_to_utc, area_coords
    Returns empty list if none active.
    """
    data = _get("airsigmet", {})
    if not data:
        return []

    sigmets = []
    for s in data:
        sigmets.append({
            "hazard": s.get("hazard"),
            "raw": s.get("rawAirSigmet"),
            "valid_from_utc": _epoch_to_iso(s.get("validTimeFrom")),
            "valid_to_utc": _epoch_to_iso(s.get("validTimeTo")),
            "area_coords": s.get("coords", []),
        })

    return sigmets


# ── G-AIRMETs ────────────────────────────────────────────────────────────────

def get_gairmets(product="all"):
    """
    Fetch active G-AIRMETs (replaced text AIRMETs for CONUS in January 2025).

    product: "sierra" (IFR/mountain obscuration), "tango" (turbulence/winds),
             "zulu" (icing/freezing level), or "all" (default)

    Returns a list of dicts, each with keys:
        product, hazard, severity, due_to,
        valid_utc, expire_utc, top_ft, base_ft, area_coords
    Returns empty list if none active.
    """
    params = {} if product == "all" else {"type": product}
    data = _get("gairmet", params)
    if not data:
        return []

    gairmets = []
    for g in data:
        top = g.get("top")
        base = g.get("base")
        gairmets.append({
            "product": g.get("product"),
            "hazard": g.get("hazard"),
            "severity": g.get("severity"),
            "due_to": g.get("due_to"),
            "valid_utc": g.get("validTime"),
            "expire_utc": _epoch_to_iso(g.get("expireTime")),
            "top_ft": int(top) * 100 if top and top.lstrip("-").isdigit() else top,
            "base_ft": int(base) * 100 if base and base.lstrip("-").isdigit() else base,
            "area_coords": g.get("coords", []),
        })

    return gairmets


# ── Winds Aloft ──────────────────────────────────────────────────────────────

# Approximate mapping: US state abbreviation → nearest winds-aloft station ID.
# Winds aloft stations use 3-letter FAA IDs (not ICAO).
_STATE_TO_WINDS_STATION = {
    "FL": "TBW", "GA": "SAV", "SC": "CHS", "NC": "GSO", "VA": "RIC",
    "MD": "DCA", "DE": "PHL", "NJ": "EWR", "NY": "ALB", "CT": "HFD",
    "MA": "BOS", "RI": "PVD", "NH": "MHT", "VT": "BTV", "ME": "PWM",
    "PA": "PIT", "OH": "CLE", "MI": "DTW", "IN": "IND", "IL": "ORD",
    "WI": "MSN", "MN": "MSP", "IA": "DSM", "MO": "STL", "KY": "LEX",
    "TN": "BNA", "AL": "BHM", "MS": "JAN", "AR": "LIT", "LA": "MSY",
    "TX": "DFW", "OK": "OKC", "KS": "ICT", "NE": "OMA", "SD": "RAP",
    "ND": "BIS", "MT": "BIL", "WY": "CPR", "CO": "DEN", "NM": "ABQ",
    "AZ": "PHX", "UT": "SLC", "NV": "LAS", "CA": "LAX", "OR": "PDX",
    "WA": "SEA", "ID": "BOI", "AK": "ANC", "HI": "HNL",
    "WV": "CRW", "CT": "HFD",
}


def get_winds_aloft(station_id):
    """
    Fetch winds aloft forecast for a given 3-letter station ID.

    Returns a dict with decoded winds for 3k, 6k, 9k, 12k ft:
        { "3000": {"dir": 270, "spd": 15, "temp_c": -2, "label": "270° @ 15 kt  -2°C"},
          "6000": {...}, "9000": {...}, "12000": {...} }
    Returns None if unavailable.
    """
    try:
        data = _get("windtemp", {
            "region": "all",
            "level":  "low",
            "site":   station_id.upper(),
        })
    except Exception:
        return None

    if not data:
        return None

    # API may return a list of station objects or a single object
    if isinstance(data, list):
        station = next(
            (s for s in data if (s.get("stationId") or "").upper() == station_id.upper()),
            data[0] if data else None,
        )
    else:
        station = data

    if not station:
        return None

    result = {}
    alt_keys = [
        ("3000",  station.get("wind3k"),  station.get("temp3k")),
        ("6000",  station.get("wind6k"),  station.get("temp6k")),
        ("9000",  station.get("wind9k"),  station.get("temp9k")),
        ("12000", station.get("wind12k"), station.get("temp12k")),
    ]
    for alt, wind_raw, temp_raw in alt_keys:
        decoded = _decode_wind_aloft(wind_raw, temp_raw)
        if decoded:
            result[alt] = decoded

    return result if result else None


def get_winds_aloft_for_state(state_abbrev):
    """
    Convenience wrapper: look up the winds aloft station for a US state
    and return the winds aloft dict.
    """
    station = _STATE_TO_WINDS_STATION.get(state_abbrev.upper())
    if not station:
        return None
    return get_winds_aloft(station)


def _decode_wind_aloft(wind_raw, temp_raw):
    """
    Decode an FAA winds aloft encoded string.

    Encoding: DDDSS  (direction in tens of degrees, speed in knots)
              or 9900  (light and variable, < 5 kt)
              or 990000 (calm / not available)

    Returns dict: { dir, spd, temp_c, label } or None.
    """
    if not wind_raw:
        return None
    wind_str = str(wind_raw).strip()

    # Light and variable
    if wind_str.startswith("9900") or wind_str == "9900":
        temp_c = _parse_temp_aloft(temp_raw)
        label = "Light & Variable"
        if temp_c is not None:
            label += f"  {temp_c:+d}°C"
        return {"dir": None, "spd": None, "temp_c": temp_c, "label": label}

    # Standard encoding: first 4 chars = DDSS
    if len(wind_str) < 4:
        return None

    try:
        dd  = int(wind_str[0:2])
        ss  = int(wind_str[2:4])

        # If direction hundreds digit > 5 → direction = (dd - 50) * 10, speed += 100
        if dd > 50:
            direction = (dd - 50) * 10
            speed     = ss + 100
        else:
            direction = dd * 10
            speed     = ss

        temp_c = _parse_temp_aloft(temp_raw)
        label  = f"{direction:03d}° @ {speed} kt"
        if temp_c is not None:
            label += f"  {temp_c:+d}°C"

        return {"dir": direction, "spd": speed, "temp_c": temp_c, "label": label}

    except (ValueError, IndexError):
        return None


def _parse_temp_aloft(temp_raw):
    """Parse the temperature field (may be string like '-08', '+06', '06', '-')."""
    if temp_raw is None:
        return None
    try:
        return int(str(temp_raw).strip())
    except (ValueError, TypeError):
        return None


# ── Convenience: full weather brief ──────────────────────────────────────────

def get_weather_brief(icao, pirep_radius_nm=100):
    """
    Fetch all weather products for a given airport in one call.

    Returns a dict with keys: metar, taf, pireps, sigmets, gairmets
    """
    return {
        "metar": get_metar(icao),
        "taf": get_taf(icao),
        "pireps": get_pireps(icao, pirep_radius_nm),
        "sigmets": get_sigmets(),
        "gairmets": get_gairmets(),
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _epoch_to_iso(epoch):
    """Convert a Unix epoch timestamp to an ISO 8601 UTC string."""
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
