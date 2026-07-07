"""
Rho — instructor module.

Handles:
  - Creating invite tokens (student → instructor)
  - Accepting invite tokens (instructor visits link)
  - Reading student flights + skill logs (cross-user, via RLS policy)
  - Saving and reading instructor skill ratings
"""

import uuid
from rho.modules.db import get_client


# ── Invite flow ────────────────────────────────────────────────────────────────

def create_invite(instructor_email=None):
    """
    Generate a new invite token for the current student.

    The student copies the resulting URL and sends it to their instructor.
    The instructor visits the URL, which triggers accept_invite().

    Parameters
    ----------
    instructor_email : str | None — optional, stored for reference only

    Returns
    -------
    str  invite token  (UUID string)
    """
    sb  = get_client()
    uid = sb.auth.get_user().user.id
    token = str(uuid.uuid4())

    sb.table("instructor_invites").insert({
        "token":            token,
        "student_id":       uid,
        "instructor_email": instructor_email,
        "status":           "pending",
    }).execute()

    return token


def accept_invite(token):
    """
    Accept an invite token.  Call this when an instructor visits the invite URL.

    1. Validates the token is pending and not expired.
    2. Creates an `instructor_students` row (status='accepted').
    3. Marks the invite as 'accepted'.

    Returns
    -------
    dict  {"ok": True, "student_id": ...}  or  {"ok": False, "error": ...}
    """
    sb = get_client()

    # Fetch the invite
    rows = (
        sb.table("instructor_invites")
        .select("*")
        .eq("token", token)
        .eq("status", "pending")
        .execute()
        .data or []
    )
    if not rows:
        return {"ok": False, "error": "Invite not found, already used, or expired."}

    invite = rows[0]
    student_id = invite["student_id"]

    try:
        instructor_id = sb.auth.get_user().user.id
    except Exception:
        return {"ok": False, "error": "You must be signed in to accept an invite."}

    if instructor_id == student_id:
        return {"ok": False, "error": "You cannot be your own instructor."}

    # Check for duplicate connection
    existing = (
        sb.table("instructor_students")
        .select("id")
        .eq("instructor_id", instructor_id)
        .eq("student_id", student_id)
        .execute()
        .data or []
    )
    if not existing:
        sb.table("instructor_students").insert({
            "instructor_id": instructor_id,
            "student_id":    student_id,
            "status":        "accepted",
        }).execute()

    # Mark invite used
    sb.table("instructor_invites").update({"status": "accepted"}).eq("token", token).execute()

    return {"ok": True, "student_id": student_id}


# ── Student data (instructor reads) ───────────────────────────────────────────

def get_student_flights(student_id):
    """
    Return all completed flights for a student.
    Requires an accepted instructor_students connection (enforced by RLS).
    """
    sb = get_client()
    resp = (
        sb.table("flights")
        .select("*")
        .eq("user_id", student_id)
        .order("flight_date", desc=True)
        .execute()
    )
    return resp.data or []


def get_student_skill_log(student_id, flight_ids):
    """
    Return student skill_log rows for a list of flight IDs.
    """
    if not flight_ids:
        return []
    sb = get_client()
    resp = (
        sb.table("skill_log")
        .select("*")
        .eq("user_id", student_id)
        .in_("flight_id", flight_ids)
        .execute()
    )
    return resp.data or []


# ── Instructor ratings ─────────────────────────────────────────────────────────

def save_instructor_ratings(flight_id, student_id, ratings):
    """
    Upsert instructor skill ratings for a single flight.

    Parameters
    ----------
    flight_id  : str  UUID
    student_id : str  UUID
    ratings    : dict  { task_id: rating_int }  e.g. {"IV-A": 3, "IV-B": 2}
                 rating: 1=Needs Work, 2=Progressing, 3=Proficient
    note       : optional per-task — for V2 (tasks currently carry no notes)
    """
    sb = get_client()
    try:
        instructor_id = sb.auth.get_user().user.id
    except Exception:
        return {"ok": False, "error": "Not signed in"}

    rows = []
    for task_id, rating in ratings.items():
        if rating not in (1, 2, 3):
            continue
        rows.append({
            "flight_id":     flight_id,
            "student_id":    student_id,
            "instructor_id": instructor_id,
            "task_id":       task_id,
            "rating":        rating,
        })

    if not rows:
        return {"ok": True, "saved": 0}

    sb.table("instructor_skill_ratings").upsert(
        rows,
        on_conflict="flight_id,instructor_id,task_id"
    ).execute()

    return {"ok": True, "saved": len(rows)}


def get_instructor_ratings(flight_id):
    """
    Return instructor ratings for a flight keyed by task_id.
    Returns dict: { task_id: {"rating": int, "note": str|None, "instructor_id": str} }
    """
    sb = get_client()
    resp = (
        sb.table("instructor_skill_ratings")
        .select("*")
        .eq("flight_id", flight_id)
        .execute()
    )
    rows = resp.data or []
    return {r["task_id"]: r for r in rows}


def get_all_student_ratings(student_id):
    """
    Return all instructor ratings for all flights of a student.
    Returns list of rating rows.
    """
    sb = get_client()
    resp = (
        sb.table("instructor_skill_ratings")
        .select("*")
        .eq("student_id", student_id)
        .execute()
    )
    return resp.data or []
