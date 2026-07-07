"""
Rho — airspace and routing module
Fetches airspace boundaries from FAA ArcGIS and generates VFR route options.

Data source: FAA AIS Class Airspace Feature Service (no API key required)
Spatial ops: shapely (pip install shapely)

Route variants:
  - direct   : straight-line great-circle route
  - pilotage : same as direct for V1 (visual landmark routing is V2)
  - avoid_c  : waypoints that skirt Class B/C/D airspace (basic lateral offset)
"""

import math
import requests
from shapely.geometry import Point, LineString, Polygon

_AIRSPACE_URL = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest"
    "/services/Class_Airspace/FeatureServer/0/query"
)
_HEADERS = {"User-Agent": "Rho/1.0 student-pilot-copilot"}

# Classes that require clearance / have specific VFR entry requirements
# Class A is always "penetrated" by any route polygon (covers all CONUS above 18,000 MSL)
# Excluded here — VFR ops are always below 18,000 MSL
CONTROLLED_CLASSES = {"B", "C", "D"}


# ── Airspace fetch ────────────────────────────────────────────────────────────

def get_airspace_near(lat, lon, radius_nm=50):
    """
    Fetch airspace polygons within radius_nm of a lat/lon point.

    Returns a list of dicts, each with:
        name, airspace_class, lower_ft, lower_ref, upper_ft, upper_ref,
        type_code, city, state, polygon (shapely Polygon)
    """
    # Convert radius to decimal degrees (rough: 1nm ≈ 1/60°)
    deg = radius_nm / 60.0

    # Bounding box spatial filter
    envelope = {
        "xmin": lon - deg,
        "ymin": lat - deg,
        "xmax": lon + deg,
        "ymax": lat + deg,
        "spatialReference": {"wkid": 4269},
    }

    resp = requests.get(
        _AIRSPACE_URL,
        params={
            "geometry": str(envelope).replace("'", '"'),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "NAME,CLASS,UPPER_VAL,UPPER_CODE,LOWER_VAL,LOWER_CODE,TYPE_CODE,CITY,STATE",
            "returnGeometry": "true",
            "f": "json",
        },
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    airspaces = []
    for feature in data.get("features", []):
        attr = feature["attributes"]
        geom = feature.get("geometry", {})
        rings = geom.get("rings", [])

        # Build shapely polygon from first ring (outer boundary)
        polygon = None
        if rings:
            try:
                coords = [(pt[0], pt[1]) for pt in rings[0]]
                polygon = Polygon(coords)
            except Exception:
                pass

        lower_val  = attr.get("LOWER_VAL")
        lower_code = attr.get("LOWER_CODE")
        upper_val  = attr.get("UPPER_VAL")
        upper_code = attr.get("UPPER_CODE")

        airspaces.append({
            "name":           attr.get("NAME") or "Unknown",
            "airspace_class": attr.get("CLASS") or "?",
            "lower_ft":       _alt_label(lower_val, lower_code),
            "upper_ft":       _alt_label(upper_val, upper_code),
            "lower_raw":      _alt_raw_ft(lower_val, lower_code),  # numeric feet for filtering
            "upper_raw":      _alt_raw_ft(upper_val, upper_code),  # numeric feet for filtering
            "type_code":      attr.get("TYPE_CODE"),
            "city":           attr.get("CITY"),
            "state":          attr.get("STATE"),
            "polygon":        polygon,
        })

    return airspaces


# ── Route generation ──────────────────────────────────────────────────────────

def generate_routes(origin_lat, origin_lon, dest_lat, dest_lon,
                    airspaces=None, cruise_alt_ft=3500):
    """
    Generate VFR route options between two points.

    origin_lat/lon : departure coordinates
    dest_lat/lon   : destination coordinates
    airspaces      : list from get_airspace_near() — if None, skips analysis
    cruise_alt_ft  : planned cruise altitude in feet MSL — used to filter
                     airspace penetrations to only those whose vertical band
                     the aircraft will fly through

    Returns a dict with keys:
        direct   : { waypoints, distance_nm, airspace_penetrations }
        avoid_c  : { waypoints, distance_nm, airspace_penetrations, note }
    """
    direct_wpts = [
        {"lat": origin_lat, "lon": origin_lon, "name": "ORIGIN"},
        {"lat": dest_lat, "lon": dest_lon, "name": "DEST"},
    ]
    dist = _haversine_nm(origin_lat, origin_lon, dest_lat, dest_lon)

    # Airspace penetration check on direct route
    penetrations = []
    if airspaces:
        line = LineString([(origin_lon, origin_lat), (dest_lon, dest_lat)])
        seen_names = set()   # deduplicate: same named airspace may appear as multiple rings
        for asp in airspaces:
            if not asp["polygon"] or asp["airspace_class"] not in CONTROLLED_CLASSES:
                continue
            if not line.intersects(asp["polygon"]):
                continue

            # Altitude filter: only flag if cruise_alt_ft falls within the vertical band
            lower = asp.get("lower_raw", 0)
            upper = asp.get("upper_raw", 99999)
            if not (lower <= cruise_alt_ft <= upper):
                continue

            # Dedup by name: keep only the first (lowest-floor) ring per named airspace
            name_key = (asp["name"], asp["airspace_class"])
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            # Compute where along the route this penetration first begins (for sort)
            entry_frac = _route_entry_fraction(line, asp["polygon"])

            penetrations.append({
                "name":       asp["name"],
                "class":      asp["airspace_class"],
                "lower":      asp["lower_ft"],
                "upper":      asp["upper_ft"],
                "_sort_frac": entry_frac,
            })

    # Sort in the order they're encountered flying from origin → dest
    penetrations.sort(key=lambda p: p.pop("_sort_frac", 0))

    # Avoid-C note
    avoid_note = None
    if penetrations:
        avoid_note = (
            "Direct route penetrates controlled airspace. "
            "Manual re-routing required — automatic avoidance is a V2 feature. "
            "Consider departing on a heading to stay clear, then resuming course."
        )

    return {
        "direct": {
            "waypoints": direct_wpts,
            "distance_nm": round(dist, 1),
            "airspace_penetrations": penetrations,
        },
        "avoid_c": {
            "waypoints": direct_wpts,
            "distance_nm": round(dist, 1),
            "airspace_penetrations": penetrations,
            "note": avoid_note,
        },
    }


def get_airspace_at_point(lat, lon, airspaces):
    """
    Return all airspace polygons that contain a given lat/lon point.
    Useful for 'am I in Class C right now?' checks.
    """
    pt = Point(lon, lat)
    return [a for a in airspaces if a["polygon"] and a["polygon"].contains(pt)]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine_nm(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles between two lat/lon points."""
    R = 3440.065  # Earth radius in nm
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _alt_label(val, code):
    """Return a human-readable altitude label."""
    if val is None:
        return "Unknown"
    if code == "SFC" or val == 0:
        return "SFC"
    if val == -9998:
        return "Unlimited"
    unit = code if code else "ft"
    return f"{int(val):,} {unit}"


def _alt_raw_ft(val, code):
    """Return numeric altitude in feet (MSL) for altitude filtering comparisons."""
    if val is None:
        return 0
    try:
        ival = int(val)
    except (ValueError, TypeError):
        return 0
    if code == "SFC" or ival == 0:
        return 0
    if ival == -9998:          # "Unlimited" sentinel
        return 99999
    if code and "FL" in str(code):
        return ival * 100      # Flight level → feet
    return ival                # Already in feet


def _route_entry_fraction(route_line, polygon):
    """
    Return the fractional distance (0.0–1.0) along route_line where the aircraft
    first enters the given airspace polygon.  Used to sort penetrations in
    flight order (origin=0 … destination=1).
    """
    try:
        intersection = route_line.intersection(polygon)
        if intersection.is_empty:
            return 0.5
        gtype = intersection.geom_type
        if gtype == "LineString":
            entry = Point(list(intersection.coords)[0])
        elif gtype == "MultiLineString":
            entry = Point(list(list(intersection.geoms)[0].coords)[0])
        elif gtype == "Point":
            entry = intersection
        elif gtype == "MultiPoint":
            entry = list(intersection.geoms)[0]
        else:
            entry = intersection.centroid
        return route_line.project(entry, normalized=True)
    except Exception:
        return 0.5
