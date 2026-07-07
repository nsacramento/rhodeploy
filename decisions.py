"""
Rho — decision capture module
Records pre-flight go/no-go decisions to Supabase for debrief and training history.

Table: decisions
    id              UUID (auto)
    created_at      TIMESTAMPTZ (auto)
    user_id         UUID — from auth.uid() via Supabase RLS
    origin          TEXT
    destination     TEXT
    recommendation  TEXT  — "GO" | "CAUTION" | "NO-GO"
    reason          TEXT
    weather_snap    JSONB — stripped-down weather snapshot at decision time
    route_snap      JSONB — route info (distance, penetrations)
    notes           TEXT  — optional pilot notes
"""

from rho.modules.db import get_client


def save_decision(brief, notes=None, user_id=None):
    """
    Save a pre-flight decision to Supabase.

    brief   : dict returned by insights.get_preflight_brief()
    notes   : optional pilot notes string
    user_id : current user UUID from auth.get_user_id()

    Returns the saved record dict.
    """
    record = {
        "origin":         brief["origin_icao"],
        "destination":    brief["dest_icao"],
        "recommendation": brief["recommendation"],
        "reason":         brief["reason"],
        "weather_snap":   _build_weather_snap(brief),
        "route_snap":     _build_route_snap(brief),
        "notes":          notes,
    }
    if user_id:
        record["user_id"] = user_id

    response = get_client().table("decisions").insert(record).execute()
    if not response.data:
        raise RuntimeError(f"Supabase insert returned no data: {response}")
    return response.data[0]


def get_decisions(limit=20):
    """Fetch the most recent decisions, newest first."""
    response = (
        get_client().table("decisions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


# ── Snapshot builders ─────────────────────────────────────────────────────────

def _build_weather_snap(brief):
    def _wx(assess):
        return {
            "category":   assess.get("category"),
            "wind_dir":   assess.get("wind_dir"),
            "wind_kt":    assess.get("wind_kt"),
            "ceiling_ft": assess.get("ceiling_ft"),
            "visibility": assess.get("visibility"),
            "temp_c":     assess.get("temp_c"),
            "dewpoint_c": assess.get("dewpoint_c"),
            "trend":      assess.get("trend"),
            "raw_metar":  assess.get("raw_metar"),
        }
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
