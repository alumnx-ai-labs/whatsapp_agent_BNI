"""crm_registration.py — new-customer registration and business-metadata
upsert against the Supabase `customers` table.

Owned by: Backend 2 (wraps into the `register_new_customer` tool in
tools.py, and backs the POST /customers endpoint used by the frontend).
Split out of the old crm_data.py so this owner never touches the same file
as crm_lookup.py (Backend 1).
"""
import time

from app.crm_lookup import find_customer_by_phone
from app.db import get_client
from app.phone_utils import normalize_phone


def register_new_customer(phone: str, name: str, business_name: str) -> dict:
    """Idempotent: if a customer with this phone number already exists
    (e.g. the registration step ran twice due to a retried webhook), returns
    the existing record instead of creating a duplicate."""
    existing = find_customer_by_phone(phone)
    if existing:
        return existing

    normalized = normalize_phone(phone)
    payload = {
        "customer_id": f"NEW_{int(time.time() * 1000)}",
        "business_name": business_name,
        "phone_number": phone,
        "normalized_phone": normalized,
        "contact_person": name,
        "sector": "unclassified",
        "business_description": "",
    }
    # on_conflict + upsert as a second idempotency layer in case of a race
    # between the existence check above and this insert.
    resp = (
        get_client()
        .table("customers")
        .upsert(payload, on_conflict="normalized_phone")
        .execute()
    )
    return resp.data[0]


def upsert_customer_metadata(payload: dict) -> dict:
    """Used by the POST /customers endpoint (React frontend business-metadata
    upload). Upserts on normalized_phone so re-submitting the same business's
    metadata updates the existing record rather than creating a duplicate."""
    normalized = normalize_phone(payload["phone_number"])
    row = {**payload, "normalized_phone": normalized}
    row.setdefault("customer_id", f"NEW_{int(time.time() * 1000)}")
    resp = get_client().table("customers").upsert(row, on_conflict="normalized_phone").execute()
    return resp.data[0]
