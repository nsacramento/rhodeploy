"""
Rho — debrief module
Records post-flight reviews linked to pre-flight decisions.

Table: debriefs
    id                  UUID (auto)
    created_at          TIMESTAMPTZ (auto)
    user_id             UUID — from auth.uid() via Supabase RLS
    decision_id         UUID → decisions.id
    flight_duration_min INTEGER
    actual_route        TEXT
    weather_actual      TEXT
    go_nogo_correct     BOOLEAN
    lessons             TEXT
    notes               TEXT
"""

from rho.modules.db import get_client


def save_debrief(
    decision_id,
    flight_duration_min=None,
    actual_route=None,
    weather_actual=None,
    go_nogo_correct=None,
    lessons=None,
    notes=None,
    user_id=None,
):
    """
    Save a post-flight debrief linked to a decision record.

    decision_id         : UUID string from decisions table
    flight_duration_min : actual flight time in minutes
    actual_route        : route flown / any deviations from plan
    weather_actual      : conditions actually encountered
    go_nogo_correct     : True/False — was the pre-flight call right in hindsight?
    lessons             : lessons learned
    notes               : freeform pilot notes
    user_id             : current user UUID from auth.get_user_id()

    Returns the saved debrief record dict.
    """
    record = {
        "decision_id":          decision_id,
        "flight_duration_min":  flight_duration_min,
        "actual_route":         actual_route,
        "weather_actual":       weather_actual,
        "go_nogo_correct":      go_nogo_correct,
        "lessons":              lessons,
        "notes":                notes,
    }
    record = {k: v for k, v in record.items() if v is not None}
    if user_id:
        record["user_id"] = user_id

    response = get_client().table("debriefs").insert(record).execute()
    if not response.data:
        raise RuntimeError(f"Supabase insert returned no data: {response}")
    return response.data[0]


def get_debrief(decision_id):
    """Fetch the debrief for a given decision_id, or None if not yet debriefed."""
    response = (
        get_client().table("debriefs")
        .select("*")
        .eq("decision_id", decision_id)
        .limit(1)
        .execute()
    )
    data = response.data
    return data[0] if data else None


def get_recent_debriefs(limit=10):
    """Fetch the most recent debriefs, newest first, joined with decision info."""
    response = (
        get_client().table("debriefs")
        .select("*, decisions(origin, destination, recommendation)")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []
