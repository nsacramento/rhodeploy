"""
Rho — authentication module
Handles user sign-up, sign-in, and session management via Supabase Auth.

Uses the shared client from db.py so that the JWT session is visible to
all other modules (logbook, decisions, debrief, acs) via auth.uid() in RLS.

Usage:
    from rho.modules.auth import sign_up, sign_in, sign_out, get_user_id

    sign_up("pilot@example.com", "password123")
    sign_in("pilot@example.com", "password123")
    user_id = get_user_id()
    sign_out()
"""

from rho.modules.db import get_client


def sign_up(email, password):
    """
    Create a new Rho account.
    Returns the user dict on success; raises on failure.
    """
    response = get_client().auth.sign_up({"email": email, "password": password})
    if not response.user:
        raise RuntimeError(f"Sign-up failed: {response}")
    return {"id": response.user.id, "email": response.user.email}


def sign_in(email, password):
    """
    Sign in to an existing Rho account.
    Returns the user dict on success; raises on failure (e.g. wrong password).
    """
    response = get_client().auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    if not response.user:
        raise RuntimeError(f"Sign-in failed: {response}")
    return {"id": response.user.id, "email": response.user.email}


def sign_out():
    """Sign out the current user."""
    get_client().auth.sign_out()


def get_current_user():
    """Return the currently signed-in user dict, or None."""
    try:
        response = get_client().auth.get_user()
        if response and response.user:
            return {"id": response.user.id, "email": response.user.email}
    except Exception:
        pass
    return None


def get_user_id():
    """
    Return the current user's UUID string, or None if not signed in.
    Pass this as user_id when saving flights, decisions, debriefs, and skills.
    """
    user = get_current_user()
    return user["id"] if user else None
