"""
Rho — airport module
Fetches airport info and runway data from FAA ArcGIS open data services.

Primary source: FAA AIS ArcGIS Feature Services (no API key required)
  Airports: https://adds-faa.opendata.arcgis.com
  Runways:  same service, joined via GLOBAL_ID → AIRPORT_ID
"""

import requests

_AIRPORT_URL = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest"
    "/services/US_Airport/FeatureServer/0/query"
)
_RUNWAY_URL = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest"
    "/services/Runways/FeatureServer/0/query"
)


def get_airport(icao):
    """
    Fetch basic airport info for a given ICAO identifier (e.g. 'KSRQ').

    Returns a dict with keys:
        icao, ident, name, city, state, elevation_ft,
        lat, lon, status, global_id
    Raises ValueError if not found.
    """
    icao = icao.upper().strip()
    resp = requests.get(
        _AIRPORT_URL,
        params={
            "where":     f"ICAO_ID='{icao}'",
            "outFields": "GLOBAL_ID,IDENT,NAME,LATITUDE,LONGITUDE,ELEVATION,ICAO_ID,SERVCITY,STATE,OPERSTATUS",
            "f":         "json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    data     = resp.json()
    features = data.get("features", [])
    if not features:
        raise ValueError(f"Airport not found: {icao}")

    attr = features[0]["attributes"]
    geom = features[0].get("geometry", {})

    return {
        "icao":         attr["ICAO_ID"],
        "ident":        attr["IDENT"],
        "name":         attr["NAME"],
        "city":         attr["SERVCITY"].title() if attr.get("SERVCITY") else "",
        "state":        attr["STATE"],
        "elevation_ft": round(attr["ELEVATION"]) if attr.get("ELEVATION") else None,
        "lat":          geom.get("y"),
        "lon":          geom.get("x"),
        "status":       attr["OPERSTATUS"],
        "global_id":    attr["GLOBAL_ID"],
    }


def get_runways(airport_global_id):
    """
    Fetch runway data for an airport using its GLOBAL_ID.

    Returns a list of dicts, each with keys:
        designator, length_ft, width_ft, surface, lighted
    """
    resp = requests.get(
        _RUNWAY_URL,
        params={
            "where":     f"AIRPORT_ID='{airport_global_id}'",
            "outFields": "DESIGNATOR,LENGTH,WIDTH,COMP_CODE,LIGHTACTV",
            "f":         "json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    data    = resp.json()
    runways = []
    for feature in data.get("features", []):
        attr = feature["attributes"]
        runways.append({
            "designator": attr["DESIGNATOR"],
            "length_ft":  int(attr["LENGTH"]) if attr.get("LENGTH") else None,
            "width_ft":   int(attr["WIDTH"])  if attr.get("WIDTH")  else None,
            "surface":    _surface_label(attr.get("COMP_CODE")),
            "lighted":    bool(attr.get("LIGHTACTV")),
        })
    runways.sort(key=lambda r: r["length_ft"] or 0, reverse=True)
    return runways


def get_airport_full(icao):
    """
    Convenience: returns airport info + runways in one call.
    """
    airport = get_airport(icao)
    airport["runways"] = get_runways(airport["global_id"])
    return airport


def get_airports_by_state(state_code):
    """
    Fetch airports with ICAO identifiers in a US state.

    state_code : 2-letter abbreviation, e.g. 'FL'

    Returns a list of dicts sorted by ICAO:
        { icao, name, city, display }
    """
    state_code = state_code.upper().strip()
    resp = requests.get(
        _AIRPORT_URL,
        params={
            "where":          f"STATE='{state_code}'",
            "outFields":      "ICAO_ID,NAME,SERVCITY",
            "returnGeometry": "false",
            "resultOffset":   0,
            "resultRecordCount": 2000,
            "f":              "json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data     = resp.json()
    airports = []
    for feature in data.get("features", []):
        attr = feature["attributes"]
        icao = (attr.get("ICAO_ID") or "").strip()
        name = (attr.get("NAME") or "").strip()
        city = (attr.get("SERVCITY") or "").strip().title()
        # Only include entries that have a K-prefix ICAO (public US airports)
        if icao and icao.startswith("K"):
            airports.append({
                "icao":    icao,
                "name":    name,
                "city":    city,
                "display": f"{icao} — {name}, {city}" if city else f"{icao} — {name}",
            })
    airports.sort(key=lambda x: x["icao"])
    return airports


def _surface_label(comp_code):
    mapping = {
        "ASPH": "Asphalt", "CONC": "Concrete", "TURF": "Turf",
        "GRVL": "Gravel",  "DIRT": "Dirt",     "WATE": "Water",
        "MATS": "Mats",    "SNOW": "Snow/Ice",
    }
    if not comp_code:
        return "Unknown"
    return mapping.get(comp_code.upper(), comp_code)
