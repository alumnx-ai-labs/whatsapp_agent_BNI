"""crm_lookup.py — customer lookup against the Supabase `customers` table.

Owned by: Backend 1 (wraps into the `lookup_customer` tool in tools.py).
Split out of the old crm_data.py so this owner never touches the same file
as crm_registration.py (Backend 2).
"""
from app.db import get_client
from app.phone_utils import normalize_phone


def find_customer_by_phone(phone: str) -> dict | None:
    target = normalize_phone(phone)
    resp = (
        get_client()
        .table("customers")
        .select("*")
        .eq("normalized_phone", target)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None
