"""
Rho — TFR (Temporary Flight Restriction) module

Fetches active TFRs from the FAA public endpoint and filters to the
route corridor between origin and destination.

IFR note: TFRs apply equally to VFR and IFR. The flight_rules param
is reserved for future altitude-based filtering (e.g. TFRs with
floor above cruise alt that don't affect IFR at FL). Always include
all TFRs in the corridor for now regardless of flight_rules.
"""

import math
import requests

_TFR_URL  = "https://tfr.faa.gov/tfr_map_ims/rest/tfrs/active"
_TIMEOUT  = 15


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _deg_to_nm(deg):
    """1 degree of latitude ≈ 60 nm."""
    return deg * 60


def _dist_point_to_segment_nm(px, py, ax, ay, bx, by):
    """
    Minimum distance in nm from point (px, py) to segment (ax,ay)-(bx,by).
    Coordinates in decimal degrees. Uses flat-earth approx (fine for <300 nm).
    """
    cos_lat = math.cos(math.radians((ay + by) / 2))
    # Convert to nm-scaled coords
    px_s = px * 60 * cos_lat;  py_s = py * 60
    ax_s = ax * 60 * cos_lat;  ay_s = ay * 60
    bx_s = bx * 60 * cos_lat;  by_s = by * 60

    dx = bx_s - ax_s;  dy = by_s - ay_s
    seg_len2 = dx*dx + dy*dy
    if seg_len2 == 0:
        return math.hypot(px_s - ax_s, py_s - ay_s)
    t = max(0.0, min(1.0, ((px_s - ax_s)*dx + (py_s - ay_s)*dy) / seg_len2))
    nx = ax_s + t*dx;  ny = ay_s + t*dy
    return math.hypot(px_s - nx, py_s - ny)


# ── FAA API parsing ───────────────────────────────────────────────────────────

def _parse_tfr_item(item):
    """
    Parse one TFR entry from the FAA response.
    Returns dict or None if essential fields are missing.
    The FAA endpoint returns varied structures; we try multiple key paths.
    """
    try:
        # Properties may be nested under 'properties', 'coreNOTAMData', or root
        props = (item.get("properties")
                 or item.get("coreNOTAMData", {}).get("notam")
                 or item)

        # Coordinates: try GeoJSON geometry first, then flat props
        lat = lon = None
        geo = item.get("geometry") or {}
        geo_type = (geo.get("type") or "").lower()
        coords    = geo.get("coordinates") or []

        if geo_type == "point" and len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
        elif geo_type == "polygon" and coords:
            # centroid of outer ring
            ring = coords[0]
            if ring:
                lon = sum(c[0] for c in ring) / len(ring)
                lat = sum(c[1] for c in ring) / len(ring)
        elif geo_type == "multipolygon" and coords:
            ring = coords[0][0] if coords[0] else []
            if ring:
                lon = sum(c[0] for c in ring) / len(ring)
                lat = sum(c[1] for c in ring) / len(ring)

        if lat is None:
            lat = float(props.get("lat") or props.get("latitude")  or 0)
            lon = float(props.get("lon") or props.get("longitude") or 0)

        if not lat and not lon:
            return None

        notam_id  = str(props.get("id") or props.get("notamId") or
                        props.get("number") or "").strip()
        tfr_type  = str(props.get("type") or props.get("classification") or "TFR")
        radius_nm = float(props.get("radius") or props.get("radius_nm") or 5)
        alt_floor = str(props.get("altitudeMSL") or props.get("altitude") or
                        props.get("lowerAlt") or "SFC")
        alt_ceil  = str(props.get("upperAlt") or props.get("ceilingAlt") or "UNLIMITED")
        summary   = str(props.get("text") or props.get("simpleFreeText") or
                        props.get("description") or "")[:300]

        return {
            "notam_id":   notam_id or "UNKNOWN",
            "tfr_type":   tfr_type,
            "radius_nm":  radius_nm,
            "lat":        lat,
            "lon":        lon,
            "alt_floor":  alt_floor,
            "alt_ceil":   alt_ceil,
            "summary":    summary,
        }
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_tfrs_near_route(lat1, lon1, lat2, lon2,
                        flight_rules="VFR", pad_nm=30):
    """
    Return active TFRs within pad_nm of the direct route segment.

    Parameters
    ----------
    lat1, lon1   : origin decimal degrees
    lat2, lon2   : destination decimal degrees
    flight_rules : "VFR" | "IFR" — reserved for future altitude filtering
    pad_nm       : corridor half-width in nm (default 30)

    Returns
    -------
    list[dict] — each dict has:
        notam_id, tfr_type, radius_nm, lat, lon,
        alt_floor, alt_ceil, summary
    Returns [] on any network/parse error — never raises.
    """
    try:
        resp = requests.get(_TFR_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()
    except Exception:
        return []

    # Normalise to list
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = (raw.get("features") or raw.get("tfrs") or
                 raw.get("items") or list(raw.values())[0]
                 if len(raw) == 1 else [])
    else:
        return []

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        tfr = _parse_tfr_item(item)
        if tfr is None:
            continue
        dist = _dist_point_to_segment_nm(
            tfr["lon"], tfr["lat"],
            lon1, lat1,
            lon2, lat2,
        )
        if dist <= tfr["radius_nm"] + pad_nm:
            results.append(tfr)

    return results
