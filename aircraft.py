"""
Rho — aircraft module.

Preset POH data for common training aircraft.
All V-speeds in KIAS. Weights in lbs. Fuel in gal. Burn in gph.

NOTE: These are representative values from published POH documents.
      Always verify against YOUR specific aircraft's POH before flight.
"""

# ── Preset aircraft types ──────────────────────────────────────────────────────
# Key format: "manufacturer_model" slug used in profiles + flights tables.

AIRCRAFT_TYPES = {
    "c152": {
        "display":           "Cessna 152",
        "manufacturer":      "Cessna",
        "model":             "152",
        "engine_hp":         110,
        # V-speeds (KIAS)
        "vx":                67,    # best angle of climb
        "vy":                75,    # best rate of climb
        "vg":                60,    # best glide
        "vs0":               43,    # stall, full flaps
        "vs1":               50,    # stall, clean
        "va":                104,   # maneuvering (at max gross)
        "vfe":               85,    # max flaps extended (first notch)
        "vno":               111,   # max structural cruise
        "vne":               149,   # never exceed
        # Weights
        "max_gross_lbs":     1670,
        "empty_weight_lbs":  1108,  # typical
        "useful_load_lbs":   562,
        # Fuel
        "fuel_capacity_gal": 26,
        "fuel_usable_gal":   24.5,
        "fuel_burn_gph":     6.1,
        # Oil
        "oil_capacity_qt":   6,
        # Performance
        "service_ceiling_ft": 14700,
        "climb_fpm":          715,
        "cruise_ktas":        107,
        "range_nm":           340,
    },
    "c172n": {
        "display":           "Cessna 172N Skyhawk",
        "manufacturer":      "Cessna",
        "model":             "172N",
        "engine_hp":         160,
        "vx":                59,
        "vy":                67,
        "vg":                65,
        "vs0":               40,
        "vs1":               48,
        "va":                96,
        "vfe":               85,
        "vno":               127,
        "vne":               158,
        "max_gross_lbs":     2300,
        "empty_weight_lbs":  1393,
        "useful_load_lbs":   907,
        "fuel_capacity_gal": 43,
        "fuel_usable_gal":   40,
        "fuel_burn_gph":     8.4,
        "oil_capacity_qt":   8,
        "service_ceiling_ft": 14200,
        "climb_fpm":          770,
        "cruise_ktas":        122,
        "range_nm":           420,
    },
    "c172s": {
        "display":           "Cessna 172S Skyhawk SP",
        "manufacturer":      "Cessna",
        "model":             "172S",
        "engine_hp":         180,
        "vx":                62,
        "vy":                74,
        "vg":                68,
        "vs0":               40,
        "vs1":               48,
        "va":                102,
        "vfe":               85,
        "vno":               129,
        "vne":               163,
        "max_gross_lbs":     2550,
        "empty_weight_lbs":  1663,
        "useful_load_lbs":   887,
        "fuel_capacity_gal": 56,
        "fuel_usable_gal":   53,
        "fuel_burn_gph":     8.4,
        "oil_capacity_qt":   8,
        "service_ceiling_ft": 14000,
        "climb_fpm":          730,
        "cruise_ktas":        124,
        "range_nm":           518,
    },
    "c182t": {
        "display":           "Cessna 182T Skylane",
        "manufacturer":      "Cessna",
        "model":             "182T",
        "engine_hp":         230,
        "vx":                64,
        "vy":                80,
        "vg":                73,
        "vs0":               43,
        "vs1":               51,
        "va":                111,
        "vfe":               140,
        "vno":               140,
        "vne":               175,
        "max_gross_lbs":     3100,
        "empty_weight_lbs":  1970,
        "useful_load_lbs":   1130,
        "fuel_capacity_gal": 87,
        "fuel_usable_gal":   83,
        "fuel_burn_gph":     13.0,
        "oil_capacity_qt":   12,
        "service_ceiling_ft": 18100,
        "climb_fpm":          924,
        "cruise_ktas":        145,
        "range_nm":           916,
    },
    "pa28_161": {
        "display":           "Piper PA-28-161 Warrior II",
        "manufacturer":      "Piper",
        "model":             "PA-28-161",
        "engine_hp":         160,
        "vx":                64,
        "vy":                79,
        "vg":                73,
        "vs0":               49,
        "vs1":               57,
        "va":                111,
        "vfe":               102,
        "vno":               126,
        "vne":               154,
        "max_gross_lbs":     2325,
        "empty_weight_lbs":  1405,
        "useful_load_lbs":   920,
        "fuel_capacity_gal": 50,
        "fuel_usable_gal":   48,
        "fuel_burn_gph":     8.5,
        "oil_capacity_qt":   8,
        "service_ceiling_ft": 11000,
        "climb_fpm":          710,
        "cruise_ktas":        117,
        "range_nm":           465,
    },
    "pa28_181": {
        "display":           "Piper PA-28-181 Archer III",
        "manufacturer":      "Piper",
        "model":             "PA-28-181",
        "engine_hp":         180,
        "vx":                68,
        "vy":                82,
        "vg":                76,
        "vs0":               49,
        "vs1":               57,
        "va":                111,
        "vfe":               102,
        "vno":               126,
        "vne":               154,
        "max_gross_lbs":     2550,
        "empty_weight_lbs":  1643,
        "useful_load_lbs":   907,
        "fuel_capacity_gal": 50,
        "fuel_usable_gal":   48,
        "fuel_burn_gph":     9.0,
        "oil_capacity_qt":   8,
        "service_ceiling_ft": 14100,
        "climb_fpm":          667,
        "cruise_ktas":        125,
        "range_nm":           465,
    },
    "pa38": {
        "display":           "Piper PA-38-112 Tomahawk",
        "manufacturer":      "Piper",
        "model":             "PA-38-112",
        "engine_hp":         112,
        "vx":                59,
        "vy":                65,
        "vg":                61,
        "vs0":               49,
        "vs1":               55,
        "va":                103,
        "vfe":               100,
        "vno":               108,
        "vne":               125,
        "max_gross_lbs":     1670,
        "empty_weight_lbs":  1128,
        "useful_load_lbs":   542,
        "fuel_capacity_gal": 32,
        "fuel_usable_gal":   30,
        "fuel_burn_gph":     6.5,
        "oil_capacity_qt":   6,
        "service_ceiling_ft": 13200,
        "climb_fpm":          718,
        "cruise_ktas":        109,
        "range_nm":           360,
    },
    "da20": {
        "display":           "Diamond DA20-C1 Eclipse",
        "manufacturer":      "Diamond",
        "model":             "DA20-C1",
        "engine_hp":         125,
        "vx":                68,
        "vy":                80,
        "vg":                77,
        "vs0":               47,
        "vs1":               53,
        "va":                129,
        "vfe":               107,
        "vno":               122,
        "vne":               175,
        "max_gross_lbs":     1764,
        "empty_weight_lbs":  1235,
        "useful_load_lbs":   529,
        "fuel_capacity_gal": 24,
        "fuel_usable_gal":   21.5,
        "fuel_burn_gph":     4.8,
        "oil_capacity_qt":   6,
        "service_ceiling_ft": 16000,
        "climb_fpm":          800,
        "cruise_ktas":        130,
        "range_nm":           392,
    },
    "da40": {
        "display":           "Diamond DA40-180",
        "manufacturer":      "Diamond",
        "model":             "DA40-180",
        "engine_hp":         180,
        "vx":                71,
        "vy":                83,
        "vg":                78,
        "vs0":               51,
        "vs1":               55,
        "va":                129,
        "vfe":               107,
        "vno":               136,
        "vne":               178,
        "max_gross_lbs":     2535,
        "empty_weight_lbs":  1680,
        "useful_load_lbs":   855,
        "fuel_capacity_gal": 40,
        "fuel_usable_gal":   36,
        "fuel_burn_gph":     9.0,
        "oil_capacity_qt":   8,
        "service_ceiling_ft": 16400,
        "climb_fpm":          1070,
        "cruise_ktas":        147,
        "range_nm":           720,
    },
}

# Ordered list for the dropdown (display name → key)
AIRCRAFT_OPTIONS = {v["display"]: k for k, v in AIRCRAFT_TYPES.items()}
# Reverse: key → display
AIRCRAFT_DISPLAY = {k: v["display"] for k, v in AIRCRAFT_TYPES.items()}


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_aircraft(type_key):
    """Return the aircraft dict for a given type key, or None."""
    return AIRCRAFT_TYPES.get(type_key)


def vspeeds_summary(ac):
    """
    Return a short plain-text V-speeds summary for use in briefs/PDFs.
    ac: dict from AIRCRAFT_TYPES
    """
    if not ac:
        return ""
    return (
        f"Vg {ac['vg']} kt  |  Vx {ac['vx']} kt  |  Vy {ac['vy']} kt  |  "
        f"Vs0 {ac['vs0']} kt  |  Vs1 {ac['vs1']} kt  |  Va {ac['va']} kt  |  "
        f"Vno {ac['vno']} kt  |  Vne {ac['vne']} kt"
    )


def fuel_endurance_hrs(ac, reserve_gal=5.0):
    """Return usable endurance in hours (minus reserve)."""
    if not ac or not ac.get("fuel_usable_gal") or not ac.get("fuel_burn_gph"):
        return None
    return round((ac["fuel_usable_gal"] - reserve_gal) / ac["fuel_burn_gph"], 1)


def max_range_nm(ac, reserve_gal=5.0):
    """Return approximate max range in nm (minus reserve fuel)."""
    hrs = fuel_endurance_hrs(ac, reserve_gal)
    if hrs is None or not ac.get("cruise_ktas"):
        return None
    return round(hrs * ac["cruise_ktas"])
