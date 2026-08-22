"""calendar_data.py — calendar integration. Stubbed by default (CALENDAR_PROVIDER=stub);
set CALENDAR_PROVIDER=hello_oscar to book against the real Hello Oscar API once
credentials are available (issue #10 — confirm the appointment by calling Hello
Oscar). Booking is idempotent: the same (customer, start_iso) pair always
resolves to the same `meetings` row instead of creating duplicates on a
retried request.
"""
import os
import random
import string

import httpx

from app.db import get_client

HELLO_OSCAR_TIMEOUT_SECONDS = 10.0


class HelloOscarError(RuntimeError):
    """Raised when the Hello Oscar API can't confirm a booking."""


def _book_via_hello_oscar(title: str, start_iso: str, duration_minutes: int, attendee_phone: str) -> dict:
    """Create the meeting in Hello Oscar and return its event id + RSVP link.

    Hello Oscar's documented v1 contract: POST /v1/events, bearer-token auth,
    JSON body, response contains `id` and `rsvp_url`. Configure via
    HELLO_OSCAR_API_BASE (defaults to the production API) and
    HELLO_OSCAR_API_KEY (required — raises a clear error if missing rather
    than failing deep inside httpx).
    """
    base_url = os.environ.get("HELLO_OSCAR_API_BASE", "https://api.hellooscar.com")
    api_key = os.environ.get("HELLO_OSCAR_API_KEY")
    if not api_key:
        raise HelloOscarError("HELLO_OSCAR_API_KEY is not set — required when CALENDAR_PROVIDER=hello_oscar")

    try:
        with httpx.Client(timeout=HELLO_OSCAR_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{base_url}/v1/events",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "title": title,
                    "start_time": start_iso,
                    "duration_minutes": duration_minutes,
                    "attendees": [{"phone": attendee_phone}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        # Surface as a domain-specific error rather than letting a raw httpx
        # exception bubble up into the LangChain tool call.
        raise HelloOscarError(f"Hello Oscar booking failed: {exc}") from exc

    return {"event_id": data["id"], "rsvp_link": data["rsvp_url"]}


def book_meeting(title: str, start_iso: str, duration_minutes: int, attendee_phone: str, customer_id: str) -> dict:
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
        fake_id = "evt_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        rsvp_link = f"https://calendar.app.google/{fake_id}"
        print(f"[calendar:stub] booking \"{title}\" at {start_iso} for {duration_minutes}min (attendee {attendee_phone})")
    elif provider == "hello_oscar":
        result = _book_via_hello_oscar(title, start_iso, duration_minutes, attendee_phone)
        rsvp_link = result["rsvp_link"]
        print(f"[calendar:hello_oscar] booked \"{title}\" at {start_iso} -> event {result['event_id']}")
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