"""
Rho — Feedback module

Stores in-app beta feedback linked to specific features.

Supabase table required (run feedback_setup.sql):
    feedback
        id          UUID (auto)
        created_at  TIMESTAMPTZ (auto)
        user_id     UUID (nullable — auth.uid())
        feature     TEXT
        rating      INTEGER (1-5, nullable)
        message     TEXT
"""

from rho.modules.db import get_client

# All features users can link feedback to
FEEDBACK_FEATURES = [
    "Pre-Flight Brief — Weather Display",
    "Pre-Flight Brief — Go/No-Go Decision",
    "Pre-Flight Brief — Airspace & Routing",
    "Pre-Flight Brief — Communications (Comms)",
    "Pre-Flight Brief — TFR Check",
    "Pre-Flight Brief — Winds Aloft",
    "Flight Documents — In-Flight Guide PDF",
    "Flight Documents — Kneeboard PDF",
    "Flight Documents — VFR Nav Log PDF",
    "Flight Log — Logbook",
    "Flight Log — ACS Skills Matrix",
    "ACS Reports — Checkride Readiness Report",
    "ACS Reports — Lesson Planner",
    "Tools — Density Altitude Calculator",
    "Tools — Weight & Balance Calculator",
    "Login / Sign Up",
    "Profile & Aircraft Setup",
    "Overall App / General",
    "Other",
]


def submit_feedback(feature, message, rating=None, user_id=None):
    """
    Save a feedback entry to Supabase.

    feature  : str — one of FEEDBACK_FEATURES
    message  : str — free-text feedback
    rating   : int 1-5 or None
    user_id  : UUID str or None

    Returns the saved record dict.
    """
    record = {
        "feature": feature,
        "message": message.strip(),
    }
    if rating is not None:
        record["rating"] = int(rating)
    if user_id:
        record["user_id"] = user_id

    resp = get_client().table("feedback").insert(record).execute()
    if not resp.data:
        raise RuntimeError("Feedback insert returned no data")
    return resp.data[0]


def get_all_feedback(limit=200):
    """
    Fetch all feedback entries, newest first.
    Returns list of dicts with: id, created_at, feature, rating, message, user_id
    """
    resp = (
        get_client()
        .table("feedback")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []
