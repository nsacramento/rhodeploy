"""
Rho — communications module
Parses FAA NASR 28-day subscription data for airport comm frequencies.

Data source: FAA NASR subscription (free download, updated every 28 days)
Download: https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/

Setup: place the downloaded ZIP at ~/rho/data/nasr_current.zip
       (or set RHO_NASR_ZIP environment variable to override)

Parses:
  TWR.txt  — Tower, Ground, Clearance Delivery, ATIS, Approach/Departure
  APT.txt  — UNICOM and CTAF (for non-towered airports)
"""

import os
import zipfile
from pathlib import Path

_DEFAULT_ZIP = Path.home() / "rho" / "data" / "nasr_current.zip"

# Module-level cache: icao → comms dict
_cache = {}

# TWR3 record layout (after 8-char header "TWR3XXXX")
_TWR3_PAIRS = 9
_FREQ_LEN   = 44
_USE_LEN    = 50

# APT record field positions (0-based)
_APT_IDENT_START  = 27   # pos 28, 4 chars (e.g. "SRQ ")
_APT_UNICOM_START = 981  # pos 982, 7 chars
_APT_CTAF_START   = 988  # pos 989, 7 chars

# Use code → human-readable label
_USE_MAP = {
    "CD":     "Clearance Delivery",
    "CD/P":   "Clearance Delivery",
    "LCL":    "Tower",
    "LCL/P":  "Tower",
    "LCL/S":  "Tower (Secondary)",
    "GND":    "Ground",
    "GND/P":  "Ground",
    "GND/S":  "Ground (Secondary)",
    "ATIS":   "ATIS",
    "UNIC":   "UNICOM",
    "CTAF":   "CTAF",
    "APCH":   "Approach",
    "APCH/P": "Approach",
    "APCH/S": "Approach (Secondary)",
    "DEP":    "Departure",
    "DEP/P":  "Departure",
    "DEP/S":  "Departure (Secondary)",
    "EMERG":  "Emergency",
}


def get_comms(icao, nasr_zip=None):
    """
    Get communication frequencies for an airport from NASR data.

    icao     : ICAO identifier (e.g. 'KSRQ')
    nasr_zip : path to NASR ZIP file. Defaults to ~/rho/data/nasr_current.zip
               or RHO_NASR_ZIP environment variable.

    Returns a dict with:
        icao, ident,
        frequencies    list of {freq, use_code, use_label}
        atis           ATIS frequency string or None
        tower          Tower frequency string or None
        ground         Ground frequency string or None
        clearance      Clearance Delivery frequency string or None
        approach       list of {freq, use_code, use_label} for approach/dep
        unicom         UNICOM frequency string or None
        ctaf           CTAF frequency string or None
        has_tower      bool
        remarks        list of remark strings
    """
    icao = icao.upper().strip()

    if icao in _cache:
        return _cache[icao]

    zip_path = (
        nasr_zip
        or os.environ.get("RHO_NASR_ZIP")
        or str(_DEFAULT_ZIP)
    )

    if not os.path.exists(zip_path):
        return _stub(
            icao,
            f"NASR ZIP not found at {zip_path}. "
            "Download from https://www.faa.gov/air_traffic/flight_info/"
            "aeronav/aero_data/NASR_Subscription/ and save as nasr_current.zip "
            "in ~/rho/data/."
        )

    # NASR uses local identifiers without the K prefix (KSRQ → SRQ)
    ident = icao[1:] if icao.startswith("K") and len(icao) == 4 else icao

    result = _parse_nasr(zip_path, ident, icao)
    _cache[icao] = result
    return result


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_nasr(zip_path, ident, icao):
    """Parse TWR.txt and APT.txt from NASR ZIP for the given airport."""
    frequencies = []
    approach    = []
    remarks     = []
    has_tower   = False
    unicom      = None
    ctaf        = None

    with zipfile.ZipFile(zip_path, "r") as zf:

        # ── TWR.txt ───────────────────────────────────────────────
        try:
            with zf.open("TWR.txt") as f:
                for raw in f:
                    line = raw.decode("latin-1").rstrip("\r\n")
                    if len(line) < 8:
                        continue
                    rec_type = line[:4]
                    rec_id   = line[4:8].strip()

                    if rec_id == ident:
                        if rec_type == "TWR1":
                            pass  # has_tower set below from LCL frequency presence

                        elif rec_type == "TWR3":
                            frequencies.extend(_parse_twr3(line))

                        elif rec_type == "TWR6":
                            remark = line[9:].strip()
                            if remark:
                                remarks.append(remark)

                    elif rec_type == "TWR7":
                        # Satellite airport approach/departure records
                        # Satellite ident appears after the freq/use pair
                        sat_section = line[102:]
                        if ident in sat_section:
                            freq = line[8:52].strip()
                            use  = line[52:102].strip()
                            if freq:
                                # Skip UHF military frequencies (> 136 MHz)
                                try:
                                    if float(freq.split()[0]) > 136:
                                        continue
                                except (ValueError, IndexError):
                                    pass
                                use_codes = use.split()
                                first     = use_codes[0] if use_codes else ""
                                if any(k in first for k in ("APCH", "DEP", "CLASS")):
                                    approach.append({
                                        "freq":      freq,
                                        "use_code":  use.strip(),
                                        "use_label": _USE_MAP.get(first, use.strip()),
                                    })
        except KeyError:
            remarks.append("[Rho] TWR.txt not found in NASR ZIP")

        # ── APT.txt — UNICOM and CTAF ─────────────────────────────
        try:
            with zf.open("APT.txt") as f:
                for raw in f:
                    line = raw.decode("latin-1").rstrip("\r\n")
                    if not line.startswith("APT"):
                        continue
                    if len(line) < _APT_IDENT_START + 4:
                        continue
                    apt_id = line[_APT_IDENT_START:_APT_IDENT_START + 4].strip()
                    if apt_id != ident:
                        continue
                    if len(line) > _APT_CTAF_START + 7:
                        unicom = line[_APT_UNICOM_START:_APT_UNICOM_START + 7].strip() or None
                        ctaf   = line[_APT_CTAF_START:_APT_CTAF_START + 7].strip() or None
                    break
        except KeyError:
            remarks.append("[Rho] APT.txt not found in NASR ZIP")

    # Convenience single-frequency lookups
    atis      = next((f["freq"] for f in frequencies if "ATIS"  in f["use_code"]), None)
    tower     = next((f["freq"] for f in frequencies if f["use_code"] in ("LCL/P", "LCL")), None)
    ground    = next((f["freq"] for f in frequencies if f["use_code"] in ("GND/P", "GND")), None)
    clearance = next((f["freq"] for f in frequencies if "CD"    in f["use_code"]), None)
    # Airport is towered only if an actual local control (tower) frequency was found
    has_tower = tower is not None

    return {
        "icao":        icao,
        "ident":       ident,
        "frequencies": frequencies,
        "atis":        atis,
        "tower":       tower,
        "ground":      ground,
        "clearance":   clearance,
        "approach":    approach,
        "unicom":      unicom,
        "ctaf":        ctaf,
        "has_tower":   has_tower,
        "remarks":     remarks,
    }


def _parse_twr3(line):
    """
    Parse a TWR3 record into a list of {freq, use_code, use_label} dicts.
    TWR3 has up to 9 frequency/use pairs after the 8-char header.
    Each pair: 44 chars freq + 50 chars use.
    Skips UHF military frequencies (> 200 MHz).
    """
    data    = line[8:]
    entries = []
    pair_sz = _FREQ_LEN + _USE_LEN

    for i in range(_TWR3_PAIRS):
        offset = i * pair_sz
        freq   = data[offset:offset + _FREQ_LEN].strip()
        use    = data[offset + _FREQ_LEN:offset + pair_sz].strip()
        if not freq:
            continue
        # Skip UHF military freqs
        try:
            if float(freq.split()[0]) > 200:
                continue
        except (ValueError, IndexError):
            pass
        use_codes = use.split()
        label     = _USE_MAP.get(use_codes[0] if use_codes else "", use)
        entries.append({"freq": freq, "use_code": use, "use_label": label})

    return entries


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stub(icao, reason):
    """Return an empty comms dict explaining why data is unavailable."""
    return {
        "icao":        icao,
        "ident":       None,
        "frequencies": [],
        "atis":        None,
        "tower":       None,
        "ground":      None,
        "clearance":   None,
        "approach":    [],
        "unicom":      None,
        "ctaf":        None,
        "has_tower":   False,
        "remarks":     [f"[Rho] {reason}"],
    }
