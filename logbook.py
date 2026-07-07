"""
Rho — Part 61 training ledger (logbook module)
Tracks flight hours and computes progress toward FAA Private Pilot Certificate
requirements under 14 CFR Part 61.109.

Table: flight_log
    id              UUID (auto)
    created_at      TIMESTAMPTZ (auto)
    user_id         UUID — from auth.uid() via Supabase RLS
    flight_date     DATE
    origin          TEXT
    destination     TEXT
    duration_min    INTEGER — flight time in minutes
    dual            BOOLEAN — flight with instructor
    solo            BOOLEAN — solo flight
    cross_country   BOOLEAN — cross-country (>50nm from departure)
    night           BOOLEAN — night flight
    instrument_hood BOOLEAN — simulated instrument time under hood
    takeoffs        INTEGER
    landings        INTEGER
    night_takeoffs  INTEGER
    night_landings  INTEGER
    remarks         TEXT

Part 61.109 Private Pilot Minimums tracked:
    40.0 hrs  total flight time
    20.0 hrs  dual (with instructor)
    10.0 hrs  solo
     3.0 hrs  dual cross-country
     3.0 hrs  dual night
     3.0 hrs  dual instrument (hood)
"""

from datetime import date
from rho.modules.db import get_client

# ── Part 61.109 requirements ─────────────────────────────────────────────────

REQUIREMENTS = {
    "total_hours":           40.0,
    "dual_hours":            20.0,
    "solo_hours":            10.0,
    "dual_xc_hours":          3.0,
    "dual_night_hours":       3.0,
    "dual_instrument_hours":  3.0,
}


# ── Log a flight ──────────────────────────────────────────────────────────────

def log_flight(
    origin,
    destination,
    duration_min,
    flight_date=None,
    dual=False,
    solo=False,
    cross_country=False,
    night=False,
    instrument_hood=False,
    takeoffs=1,
    landings=1,
    night_takeoffs=0,
    night_landings=0,
    remarks=None,
    user_id=None,
):
    """
    Log a flight to the training ledger.

    origin/destination : ICAO identifiers
    duration_min       : total flight time in minutes
    flight_date        : date object or ISO string; defaults to today
    dual               : True if flight instructor was on board
    solo               : True if student flew alone
    cross_country      : True if >50nm from departure point
    night              : True if night flight
    instrument_hood    : True if simulated instrument time logged
    takeoffs/landings  : counts for the flight
    night_takeoffs/landings : night-specific counts
    remarks            : freeform notes
    user_id            : current user's UUID (from auth.get_user_id()); required
                         for RLS — pass this from the app layer

    Returns the saved flight record dict.
    """
    if flight_date is None:
        flight_date = date.today().isoformat()
    elif hasattr(flight_date, "isoformat"):
        flight_date = flight_date.isoformat()

    record = {
        "flight_date":     flight_date,
        "origin":          origin.upper(),
        "destination":     destination.upper(),
        "duration_min":    int(duration_min),
        "dual":            bool(dual),
        "solo":            bool(solo),
        "cross_country":   bool(cross_country),
        "night":           bool(night),
        "instrument_hood": bool(instrument_hood),
        "takeoffs":        int(takeoffs),
        "landings":        int(landings),
        "night_takeoffs":  int(night_takeoffs),
        "night_landings":  int(night_landings),
        "remarks":         remarks,
    }

    if user_id:
        record["user_id"] = user_id

    response = get_client().table("flight_log").insert(record).execute()

    if not response.data:
        raise RuntimeError(f"Supabase insert returned no data: {response}")

    return response.data[0]


# ── Retrieve flights ──────────────────────────────────────────────────────────

def get_flights(limit=50):
    """Return flight log entries for the current user, newest first."""
    response = (
        get_client().table("flight_log")
        .select("*")
        .order("flight_date", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


# ── Progress toward Part 61 checkride ────────────────────────────────────────

def get_progress():
    """
    Compute training progress against Part 61.109 Private Pilot minimums.

    Returns a dict with:
        totals    — accumulated hours/counts across all flights
        progress  — each requirement: {required, logged, remaining, met}
        summary   — plain-English readout
        flights   — total number of flights logged
    """
    flights = get_flights(limit=500)

    totals = {
        "total_min":           0,
        "dual_min":            0,
        "solo_min":            0,
        "dual_xc_min":         0,
        "dual_night_min":      0,
        "dual_instrument_min": 0,
        "total_takeoffs":      0,
        "total_landings":      0,
        "night_takeoffs":      0,
        "night_landings":      0,
    }

    for f in flights:
        dur = f.get("duration_min") or 0
        totals["total_min"]      += dur
        totals["total_takeoffs"] += f.get("takeoffs") or 0
        totals["total_landings"] += f.get("landings") or 0
        totals["night_takeoffs"] += f.get("night_takeoffs") or 0
        totals["night_landings"] += f.get("night_landings") or 0

        if f.get("dual"):
            totals["dual_min"] += dur
            if f.get("cross_country"):
                totals["dual_xc_min"] += dur
            if f.get("night"):
                totals["dual_night_min"] += dur
            if f.get("instrument_hood"):
                totals["dual_instrument_min"] += dur

        if f.get("solo"):
            totals["solo_min"] += dur

    def hrs(minutes):
        return round(minutes / 60, 1)

    logged = {
        "total_hours":           hrs(totals["total_min"]),
        "dual_hours":            hrs(totals["dual_min"]),
        "solo_hours":            hrs(totals["solo_min"]),
        "dual_xc_hours":         hrs(totals["dual_xc_min"]),
        "dual_night_hours":      hrs(totals["dual_night_min"]),
        "dual_instrument_hours": hrs(totals["dual_instrument_min"]),
    }

    progress = {}
    for key, required in REQUIREMENTS.items():
        logged_val = logged.get(key, 0.0)
        remaining  = max(0.0, round(required - logged_val, 1))
        progress[key] = {
            "required":  required,
            "logged":    logged_val,
            "remaining": remaining,
            "met":       logged_val >= required,
        }

    met_count = sum(1 for p in progress.values() if p["met"])
    summary = (
        f"{met_count}/{len(REQUIREMENTS)} hour requirements met — "
        f"{logged['total_hours']:.1f} of {REQUIREMENTS['total_hours']:.0f} total hrs, "
        f"{logged['solo_hours']:.1f} solo, {logged['dual_hours']:.1f} dual."
    )

    return {
        "totals":   totals,
        "logged":   logged,
        "progress": progress,
        "summary":  summary,
        "flights":  len(flights),
    }
