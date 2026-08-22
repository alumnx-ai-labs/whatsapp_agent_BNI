"""calendar_data.py — calendar integration. Stubbed by default (CALENDAR_PROVIDER=stub);
set CALENDAR_PROVIDER=hello_oscar to route bookings through the real Hello Oscar
API (issue #10 — confirm the appointment by calling Hello Oscar). Booking is
idempotent: the same (customer, start_iso) pair always resolves to the same
`meetings` row instead of creating duplicates on a retried request.

Hello Oscar's actual contract (per review on PR #16): a single unauthenticated
chat endpoint, {OSCAR_API_BASE_URL}/chat, that takes a free-text natural-language
instruction rather than structured event fields. No API key needed — only the
base URL, which only has to be set in the deployed environment (not required to
write or test this module).
"""
import os
from datetime import datetime, timedelta

import httpx

from app.db import get_client

OSCAR_TIMEOUT_SECONDS = 10.0
OSCAR_USER_ID = 5  # fixed constant per Hello Oscar's contract — not per-customer


class HelloOscarError(RuntimeError):
    """Raised when the Hello Oscar API can't confirm a booking."""


def _format_hour(dt: datetime) -> str:
    """'17:00' -> '5 pm' (no platform-specific strftime flags, so this works
    the same on Windows dev machines and Linux servers)."""
    hour = dt.strftime("%I").lstrip("0") or "12"
    return f"{hour} {dt.strftime('%p').lower()}"


def _build_oscar_message(title: str, start_iso: str, duration_minutes: int, attendee_name: str, location: str | None = None) -> str:
    """Build the free-text instruction Hello Oscar expects: day + start/end
    time, the literal word "Vijender", and who's attending are always
    included. Location is added only if we have one — this bot doesn't
    currently ask the customer for a meeting location, so for now that part
    of the sentence is simply left out rather than guessed or faked.
    """
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    day_name = start_dt.strftime("%A")
    where = f" at {location}" if location else ""
    return (
        f"Schedule a meeting with Vijender on {day_name} "
        f"{_format_hour(start_dt)} to {_format_hour(end_dt)}{where}. "
        f"{attendee_name} is the one attending, regarding: {title}."
    )


def _book_via_hello_oscar(message: str) -> dict:
    """POST the natural-language scheduling request to Hello Oscar's /chat
    endpoint. No auth header — the API is unauthenticated. Response shape is
    unverified (no live call has been made yet against the real API), so this
    parses defensively: it doesn't assume any particular schema beyond
    checking for an `error` key.
    """
    base_url = os.environ.get("OSCAR_API_BASE_URL")
    if not base_url:
        raise HelloOscarError("OSCAR_API_BASE_URL is not set — required when CALENDAR_PROVIDER=hello_oscar")

    try:
        with httpx.Client(timeout=OSCAR_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{base_url}/chat",
                json={"user_id": OSCAR_USER_ID, "message": message},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        # Surface as a domain-specific error rather than letting a raw httpx
        # exception bubble up into the LangChain tool call.
        raise HelloOscarError(f"Hello Oscar booking failed: {exc}") from exc

    if isinstance(data, dict) and data.get("error"):
        raise HelloOscarError(f"Hello Oscar returned an error: {data['error']}")

    # Defensive extraction: try the field names that would plausibly hold
    # Oscar's reply text, but never assume one is present.
    reply_text = None
    if isinstance(data, dict):
        for key in ("response", "reply", "message", "result"):
            if isinstance(data.get(key), str):
                reply_text = data[key]
                break

    return {"raw": data, "reply": reply_text}


def book_meeting(
    title: str,
    start_iso: str,
    duration_minutes: int,
    attendee_phone: str,
    customer_id: str,
    attendee_name: str | None = None,
    location: str | None = None,
) -> dict:
    idempotency_key = f"{customer_id}:{start_iso}"

    existing = (
        get_client()
        .table("meetings")
        .select("*")
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        return {
            "id": row["id"],
            "title": row["title"],
            "start_iso": row["start_iso"],
            "duration_minutes": duration_minutes,
            "rsvp_link": row["rsvp_link"],
        }

    provider = os.environ.get("CALENDAR_PROVIDER", "stub")
    if provider == "stub":
        import random
        import string

        fake_id = "evt_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        rsvp_link = f"https://calendar.app.google/{fake_id}"
        print(f"[calendar:stub] booking \"{title}\" at {start_iso} for {duration_minutes}min (attendee {attendee_phone})")
    elif provider == "hello_oscar":
        message = _build_oscar_message(
            title=title,
            start_iso=start_iso,
            duration_minutes=duration_minutes,
            attendee_name=attendee_name or attendee_phone,
            location=location,
        )
        result = _book_via_hello_oscar(message)
        rsvp_link = result["reply"] or "Booking request sent to Hello Oscar — awaiting confirmation."
        print(f"[calendar:hello_oscar] sent \"{message}\" -> {result['raw']}")
    else:
        raise NotImplementedError(f"CALENDAR_PROVIDER={provider} not implemented yet")

    row = (
        get_client()
        .table("meetings")
        .insert(
            {
                "customer_id": customer_id,
                "idempotency_key": idempotency_key,
                "start_iso": start_iso,
                "title": title,
                "rsvp_link": rsvp_link,
                "status": "confirmed",
            }
        )
        .execute()
        .data[0]
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "start_iso": row["start_iso"],
        "duration_minutes": duration_minutes,
        "rsvp_link": row["rsvp_link"],
    }