"""
Rho — unified flights module

One record per flight, covering the full lifecycle:
    pre-flight brief  →  in-flight  →  post-flight log + debrief

Status values:
    'in-progress'  brief done, Go selected, not yet landed / logged
    'completed'    flight log + debrief filled in after landing
    'no-go'        brief done, No-Go selected (not flown, archived)

Table: flights
    id              UUID (auto)
    created_at      TIMESTAMPTZ (auto)
    user_id         UUID — Supabase Auth user
    status          TEXT

    -- Pre-flight brief (set at brief time)
    origin          TEXT
    destination     TEXT
    cruise_alt_ft   INTEGER
    planned_date    DATE
    recommendation  TEXT    — GO / CAUTION / NO-GO
    reason          TEXT
    weather_snap    JSONB
    route_snap      JSONB
    pilot_notes     TEXT

    -- Flight log (set after landing)
    flight_date     DATE
    duration_min    INTEGER
    dual            BOOLEAN
    solo            BOOLEAN
    cross_country   BOOLEAN
    night           BOOLEAN
    instrument_hood BOOLEAN
    takeoffs        INTEGER
    landings        INTEGER
    night_takeoffs  INTEGER
    night_landings  INTEGER
    remarks         TEXT

    -- Debrief (set after landing, same form as log)
    actual_route    TEXT
    weather_actual  TEXT
    go_nogo_correct BOOLEAN
    lessons         TEXT
    debrief_notes   TEXT
"""

from datetime import date as _date
from rho.modules.db import get_client

# Part 61.109 requirements (kept here so flights.get_progress() is self-contained)
REQUIREMENTS = {
    "total_hours":           40.0,
    "dual_hours":            20.0,
    "solo_hours":            10.0,
    "dual_xc_hours":          3.0,
    "dual_night_hours":       3.0,
    "dual_instrument_hours":  3.0,
}

LABELS = {
    "total_hours":           "Total flight time",
    "dual_hours":            "Dual (with CFI)",
    "solo_hours":            "Solo",
    "dual_xc_hours":         "Dual cross-country",
    "dual_night_hours":      "Dual night",
    "dual_instrument_hours": "Dual instrument (hood)",
}


# ── Create / update ───────────────────────────────────────────────────────────

def create_flight(brief, status="in-progress", pilot_notes=None, user_id=None,
                  aircraft_type=None, tail_number=None, brief_at=None):
    """
    Create a new flight record from a pre-flight brief.

    brief         : dict from insights.get_preflight_brief()
    status        : 'in-progress' (GO) or 'no-go' (NO-GO)
    pilot_notes   : optional pilot notes entered at brief time
    user_id       : current user UUID from auth.get_user_id()
    aircraft_type : key from AIRCRAFT_TYPES (e.g. 'c172s')
    tail_number   : tail number (e.g. 'N12345')
    brief_at      : ISO timestamp string of when brief was generated

    Returns the saved flight record dict.
    """
    record = {
        "origin":         brief["origin_icao"],
        "destination":    brief["dest_icao"],
        "cruise_alt_ft":  brief.get("cruise_alt_ft"),
        "planned_date":   _date.today().isoformat(),
        "recommendation": brief["recommendation"],
        "reason":         brief["reason"],
        "weather_snap":   _build_weather_snap(brief),
        "route_snap":     _build_route_snap(brief),
        "pilot_notes":    pilot_notes,
        "status":         status,
    }
    if user_id:
        record["user_id"] = user_id
    if aircraft_type:
        record["aircraft_type"] = aircraft_type
    if tail_number:
        record["tail_number"] = (tail_number or "").strip() or None
    if brief_at:
        record["brief_at"] = brief_at

    resp = get_client().table("flights").insert(record).execute()
    if not resp.data:
        raise RuntimeError(f"Failed to create flight: {resp}")
    return resp.data[0]


def complete_flight(flight_id, log_data, user_id=None):
    """
    Finalize a flight with post-flight log + debrief data.
    Sets status to 'completed'.

    log_data keys (all optional unless noted):
        flight_date     : date object or ISO string  (required)
        duration_min    : int  (required)
        dual            : bool
        solo            : bool
        cross_country   : bool
        night           : bool
        instrument_hood : bool
        takeoffs        : int
        landings        : int
        night_takeoffs  : int
        night_landings  : int
        remarks         : str
        actual_route    : str
        weather_actual  : str
        go_nogo_correct : bool
        lessons         : str
        debrief_notes   : str

    Returns the updated flight record dict.
    """
    update = dict(log_data)
    update["status"] = "completed"

    # Normalise date
    fd = update.get("flight_date")
    if fd and hasattr(fd, "isoformat"):
        update["flight_date"] = fd.isoformat()

    resp = (
        get_client().table("flights")
        .update(update)
        .eq("id", flight_id)
        .execute()
    )
    if not resp.data:
        raise RuntimeError(f"Failed to complete flight {flight_id}: {resp}")
    return resp.data[0]


def create_manual_flight(origin, destination, duration_min, flight_date=None,
                         dual=False, solo=False, cross_country=False, night=False,
                         instrument_hood=False, takeoffs=1, landings=1,
                         night_takeoffs=0, night_landings=0, remarks=None,
                         user_id=None):
    """
    Log a past flight directly (no pre-flight brief).
    Creates a completed flight record immediately.
    """
    if flight_date is None:
        flight_date = _date.today().isoformat()
    elif hasattr(flight_date, "isoformat"):
        flight_date = flight_date.isoformat()

    record = {
        "origin":          origin.upper(),
        "destination":     destination.upper(),
        "status":          "completed",
        "planned_date":    flight_date,
        "flight_date":     flight_date,
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

    resp = get_client().table("flights").insert(record).execute()
    if not resp.data:
        raise RuntimeError(f"Failed to create manual flight: {resp}")
    return resp.data[0]


def delete_flight(flight_id):
    """
    Delete a flight record. CASCADE on skill_log.flight_id removes skill entries.
    """
    get_client().table("flights").delete().eq("id", flight_id).execute()


# ── Queries ───────────────────────────────────────────────────────────────────

def get_active_flights():
    """Return in-progress flights for the current user, newest first."""
    resp = (
        get_client().table("flights")
        .select("*")
        .eq("status", "in-progress")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_flights(limit=50, status=None):
    """
    Return flights newest first.
    status : filter to 'in-progress', 'completed', or 'no-go'. None = all.
    """
    q = (
        get_client().table("flights")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def get_flight(flight_id):
    """Fetch a single flight by ID. Returns dict or None."""
    resp = (
        get_client().table("flights")
        .select("*")
        .eq("id", flight_id)
        .limit(1)
        .execute()
    )
    data = resp.data
    return data[0] if data else None


# ── Part 61 progress ──────────────────────────────────────────────────────────

def get_progress():
    """
    Compute Part 61.109 training progress from completed flights.

    Returns dict with: totals, logged, progress, flights, summary
    """
    flights = get_flights(limit=500, status="completed")

    totals = {
        "total_min": 0, "dual_min": 0, "solo_min": 0,
        "dual_xc_min": 0, "dual_night_min": 0, "dual_instrument_min": 0,
        "total_takeoffs": 0, "total_landings": 0,
        "night_takeoffs": 0, "night_landings": 0,
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
            if f.get("cross_country"):   totals["dual_xc_min"] += dur
            if f.get("night"):           totals["dual_night_min"] += dur
            if f.get("instrument_hood"): totals["dual_instrument_min"] += dur
        if f.get("solo"):
            totals["solo_min"] += dur

    def hrs(m):
        return round(m / 60, 1)

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
        lv        = logged.get(key, 0.0)
        remaining = max(0.0, round(required - lv, 1))
        progress[key] = {
            "required":  required,
            "logged":    lv,
            "remaining": remaining,
            "met":       lv >= required,
        }

    met = sum(1 for p in progress.values() if p["met"])
    return {
        "totals":   totals,
        "logged":   logged,
        "progress": progress,
        "flights":  len(flights),
        "summary":  (
            f"{met}/{len(REQUIREMENTS)} hour requirements met — "
            f"{logged['total_hours']:.1f} of {REQUIREMENTS['total_hours']:.0f} total hrs, "
            f"{logged['solo_hours']:.1f} solo, {logged['dual_hours']:.1f} dual."
        ),
    }


# ── Snapshot helpers ──────────────────────────────────────────────────────────

def _build_weather_snap(brief):
    def _wx(a):
        return {k: a.get(k) for k in (
            "category", "wind_dir", "wind_kt", "ceiling_ft",
            "visibility", "temp_c", "dewpoint_c", "trend", "raw_metar",
        )}
    return {
        "origin":      _wx(brief.get("origin_assess") or {}),
        "destination": _wx(brief.get("dest_assess") or {}),
        "hazards":     (brief.get("hazards") or [])[:10],
    }


def _build_route_snap(brief):
    route = brief.get("route")
    if not route:
        return None
    direct = route.get("direct") or {}
    return {
        "distance_nm":           direct.get("distance_nm"),
        "airspace_penetrations": direct.get("airspace_penetrations", []),
    }
