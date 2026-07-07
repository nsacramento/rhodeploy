"""
Rho — shared Supabase client

Single client instance shared across ALL modules.
auth.sign_in() stores the JWT on this client, which is then automatically
included as the Authorization header in all subsequent database operations —
satisfying Supabase RLS policies that check auth.uid().

Import pattern for all modules:
    from rho.modules.db import get_client
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

_client = None


def get_client():
    """Return the shared Supabase client, creating it on first call."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in ~/rho/.env"
            )
        _client = create_client(url, key)
    return _client
