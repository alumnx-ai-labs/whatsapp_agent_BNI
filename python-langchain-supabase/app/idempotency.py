"""idempotency.py — two idempotency mechanisms:

1. mark_message_processed(message_id, phone) — dedupes inbound WhatsApp webhook
   deliveries. Twilio/Meta retry on timeout or non-2xx response, which would
   otherwise cause the same message to be run through the state machine twice
   (e.g. double-booking a meeting, or double-incrementing elaboration_attempts).

2. get_cached_response / store_cached_response — generic Idempotency-Key
   support for the REST API (used by POST /customers). If the frontend retries
   a submission (e.g. after a network blip) with the same Idempotency-Key
   header, we return the original response instead of creating a duplicate.
"""
from app.db import get_client


def mark_message_processed(message_id: str | None, phone: str) -> bool:
    """Returns True if this message should be processed (first time seen),
    False if it's a duplicate delivery that should be skipped."""
    if not message_id:
        # No provider message id available (e.g. local console testing) —
        # always process. Real providers (Twilio/Meta) always supply one.
        return True

    existing = (
        get_client()
        .table("processed_messages")
        .select("message_id")
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return False

    get_client().table("processed_messages").insert(
        {"message_id": message_id, "phone_number": phone}
    ).execute()
    return True


def get_cached_response(idempotency_key: str | None) -> dict | None:
    if not idempotency_key:
        return None
    resp = (
        get_client()
        .table("api_idempotency_keys")
        .select("response_body")
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    return resp.data[0]["response_body"] if resp.data else None


def store_cached_response(idempotency_key: str | None, response_body: dict) -> None:
    if not idempotency_key:
        return
    get_client().table("api_idempotency_keys").insert(
        {"idempotency_key": idempotency_key, "response_body": response_body}
    ).execute()
