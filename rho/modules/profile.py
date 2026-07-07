"""
Rho — user profile module.

Each Supabase auth user has exactly one row in the `profiles` table.
Profile is created/updated on sign-up and editable from the Profile page.

Roles
-----
  student    — default; can fly, log skills, receive instructor ratings
  instructor — can send invites, view student flights, leave ratings
"""

from rho.modules.db import get_client


# ── Write ──────────────────────────────────────────────────────────────────────

def create_or_update_profile(full_name, role="student", aircraft_type=None, tail_number=None):
    """
    Upsert the current user's profile row.

    Parameters
    ----------
    full_name     : str
    role          : "student" | "instructor"
    aircraft_type : str or None — key from AIRCRAFT_TYPES (e.g. 'c172s')
    tail_number   : str or None — e.g. 'N12345'

    Returns
    -------
    dict  profile row  or  None on failure
    """
    sb    = get_client()
    uid   = sb.auth.get_user().user.id
    email = sb.auth.get_user().user.email

    tail = (tail_number or "").strip() or None
    payload = {
        "id":            uid,
        "email":         email,
        "full_name":     full_name,
        "role":          role,
        "aircraft_type": aircraft_type or None,
        "tail_number":   tail,
    }
    resp = sb.table("profiles").upsert(payload).execute()
    rows = resp.data or []
    return rows[0] if rows else None


# ── Read ───────────────────────────────────────────────────────────────────────

def get_profile(user_id=None):
    """
    Return a profile dict for user_id (or the current user if None).
    Returns None if not found.
    """
    sb = get_client()
    if user_id is None:
        try:
            user_id = sb.auth.get_user().user.id
        except Exception:
            return None

    resp = sb.table("profiles").select("*").eq("id", user_id).execute()
    rows = resp.data or []
    return rows[0] if rows else None


def get_my_students():
    """
    Return a list of profile dicts for students linked to the current instructor.
    Only returns accepted connections.
    """
    sb  = get_client()
    uid = sb.auth.get_user().user.id

    # Fetch accepted instructor_students rows where instructor_id = current user
    links = (
        sb.table("instructor_students")
        .select("student_id, status")
        .eq("instructor_id", uid)
        .eq("status", "accepted")
        .execute()
        .data or []
    )
    if not links:
        return []

    student_ids = [r["student_id"] for r in links]
    profiles = (
        sb.table("profiles")
        .select("*")
        .in_("id", student_ids)
        .execute()
        .data or []
    )
    return profiles


def get_my_instructor():
    """
    Return the instructor's profile dict for the current student.
    Returns None if no accepted instructor connection exists.
    """
    sb  = get_client()
    uid = sb.auth.get_user().user.id

    link = (
        sb.table("instructor_students")
        .select("instructor_id, status")
        .eq("student_id", uid)
        .eq("status", "accepted")
        .limit(1)
        .execute()
        .data or []
    )
    if not link:
        return None

    instructor_id = link[0]["instructor_id"]
    return get_profile(instructor_id)


def get_pending_invites():
    """
    Return outbound pending invites created by the current user (student).
    """
    sb  = get_client()
    uid = sb.auth.get_user().user.id
    resp = (
        sb.table("instructor_invites")
        .select("*")
        .eq("student_id", uid)
        .eq("status", "pending")
        .execute()
    )
    return resp.data or []
