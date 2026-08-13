"""db.py — Supabase (Postgres) client. Every data-access module (crm, context,
pain_point_agent's taxonomy loader, session_store, calendar) goes through this
single client rather than reading local CSV/JSON files.
"""
import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    # Use the service-role key on the backend (bypasses row-level security) —
    # never expose this key to the React frontend, which should only ever
    # talk to our own FastAPI endpoints, not Supabase directly.
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
