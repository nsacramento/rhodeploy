"""
Rho — communications module
Fetches airport frequency data from OurAirports public CSV dataset.
https://ourairports.com/data/airport-frequencies.csv

Data is cached module-level after first download (~2 MB, once per process).
Subsequent lookups within the same Streamlit session are O(1) from the dict.

Returned comms dict:
    icao        str
    tower       str or None      — primary tower frequency
    ground      str or None      — primary ground frequency
    atis        str or None      — ATIS / D-ATIS, else AWOS/ASOS (see wx_label)
    wx_label    str              — "ATIS" | "AWOS" | "ASOS" — what the atis freq actually is
    clearance   str or None      — clearance delivery
    unicom      str or None      — UNICOM
    ctaf        str or None      — CTAF
    approach    list[dict]       — approach/departure {freq, use_code, use_label, facility}
                                   facility e.g. "Tampa" (from "TAMPA APP/DEP"), may be ""
    frequencies list[dict]       — all records {type, description, freq}
    has_tower   bool
"""

import io
import csv
import requests

_FREQS_URL = "https://ourairports.com/data/airport-frequencies.csv"

# Module-level cache: ICAO -> list of {type, description, freq}
_by_icao = {}
_loaded  = False

# OurAirports type code -> our comms key
_TYPE_KEY = {
    "TOWER":     "tower",
    "TWR":       "tower",
    "LCL/P":     "tower",
    "LCL":       "tower",
    "GROUND":    "ground",
    "GND/P":     "ground",
    "GND":       "ground",
    "ATIS":      "atis",
    "D-ATIS":    "atis",
    "AWOS":      "awos",
    "AWOS-3":    "awos",
    "AWOS-3P":   "awos",
    "ASOS":      "awos",
    "WXAS":      "awos",
    "UNICOM":    "unicom",
    "UNIC":      "unicom",
    "CTAF":      "ctaf",
    "CTAF/UNICOM": "ctaf_unicom",
    "APP":       "approach",
    "APCH":      "approach",
    "APCH/P":    "approach",
    "DEP":       "approach",
    "DEP/P":     "approach",
    "A/D":       "approach",
    "APP/DEP":   "approach",
    "ARR":       "approach",
    "CLEARANCE": "clearance",
    "CLD":       "clearance",
    "CD":        "clearance",
    "CD/P":      "clearance",
}


def _load():
    """Download and parse OurAirports frequency CSV into module-level dict."""
    global _by_icao, _loaded
    if _loaded:
        return
    try:
        resp = requests.get(_FREQS_URL, timeout=30)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            icao = (row.get("airport_ident") or "").strip().upper()
            if not icao:
                continue
            _by_icao.setdefault(icao, []).append({
                "type":        (row.get("type") or "").strip().upper(),
                "description": (row.get("description") or "").strip(),
                "freq":        (row.get("frequency_mhz") or "").strip(),
            })
    except Exception:
        pass  # fail silently — comms will be empty rather than crashing
    _loaded = True


def get_comms(icao):
    """
    Return communications dict for the given ICAO identifier.
    Always returns a dict (values may be None if data unavailable).
    """
    _load()
    icao    = icao.upper().strip()
    records = _by_icao.get(icao, [])

    out = {
        "icao":        icao,
        "tower":       None,
        "ground":      None,
        "atis":        None,
        "wx_label":    "ATIS",
        "clearance":   None,
        "unicom":      None,
        "ctaf":        None,
        "approach":    [],
        "frequencies": records,
        "has_tower":   False,
    }

    seen_approach = set()
    awos = None
    awos_label = "AWOS"

    for r in records:
        t    = r["type"]
        freq = r["freq"]
        desc = (r.get("description") or "").upper()
        if not freq:
            continue

        key = _TYPE_KEY.get(t)
        # Some records hide the real use in the description (e.g. UNIC "CTAF/UNICOM")
        if key == "unicom" and "CTAF" in desc:
            key = "ctaf_unicom"

        if key == "tower" and out["tower"] is None:
            out["tower"]     = freq
            out["has_tower"] = True

        elif key == "ground" and out["ground"] is None:
            out["ground"] = freq

        elif key == "atis" and out["atis"] is None:
            out["atis"] = freq

        elif key == "awos" and awos is None:
            awos = freq
            awos_label = "ASOS" if t == "ASOS" or "ASOS" in desc else "AWOS"

        elif key == "clearance" and out["clearance"] is None:
            out["clearance"] = freq

        elif key == "unicom" and out["unicom"] is None:
            out["unicom"] = freq

        elif key == "ctaf" and out["ctaf"] is None:
            out["ctaf"] = freq

        elif key == "ctaf_unicom":
            if out["ctaf"] is None:
                out["ctaf"] = freq
            if out["unicom"] is None:
                out["unicom"] = freq

        elif key == "approach" and freq not in seen_approach:
            try:
                if float(freq) < 136:
                    out["approach"].append({
                        "freq": freq, "use_code": t, "use_label": r.get("description") or t,
                        "facility": _facility_name(desc),
                    })
                    seen_approach.add(freq)
            except ValueError:
                pass

    if out["atis"] is None and awos:
        out["atis"] = awos
        out["wx_label"] = awos_label

    # Non-towered field with only a UNICOM listed: UNICOM is the CTAF
    if not out["has_tower"] and out["ctaf"] is None and out["unicom"]:
        out["ctaf"] = out["unicom"]

    return out


def _facility_name(desc):
    """'TAMPA APP/DEP' -> 'Tampa'; 'APP/DEP' -> ''."""
    words = []
    for w in desc.replace("/", " ").split():
        if w in ("APP", "DEP", "APCH", "ARR", "CLNC", "DEL", "CON", "CONTROL",
                 "APPROACH", "DEPARTURE", "SECTOR", "HIGH", "LOW"):
            break
        words.append(w)
    return " ".join(words).title()
