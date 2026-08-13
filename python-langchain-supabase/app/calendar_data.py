"""calendar_data.py — calendar integration. Stubbed by default (CALENDAR_PROVIDER=stub);
swap in the real Google Calendar API once credentials are available. Booking is
idempotent: the same (customer, start_iso) pair always resolves to the same
`meetings` row instead of creating duplicates on a retried request.
"""
import os
import random
import string

from app.db import get_client


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
    else:
        # --- Real Google Calendar integration goes here ---
        # from googleapiclient.discovery import build
        # service = build("calendar", "v3", credentials=creds)
        # event = service.events().insert(calendarId="primary", body={...}).execute()
        # rsvp_link = event["htmlLink"]
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
