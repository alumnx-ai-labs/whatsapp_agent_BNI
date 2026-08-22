"""calendar_data.py — calendar integration. Stubbed by default (CALENDAR_PROVIDER=stub);
swap in the real Google Calendar API once credentials are available. Booking is
idempotent: the same (customer, start_iso) pair always resolves to the same
`meetings` row instead of creating duplicates on a retried request.
"""
import os
import random
import string
import time

from postgrest.exceptions import APIError

from app.db import get_client

# Empirically, a customer inserted moments earlier can still trip
# meetings_customer_id_fkey on the very next request — the row shows up if you
# just check again a moment later, so this is a transient consistency gap
# (Supabase's pooled/replicated Postgres), not a real "customer doesn't
# exist" case. Retry briefly instead of failing the whole booking.
FK_VIOLATION = "23503"
CUSTOMER_FK_RETRY_DELAYS = (0.5, 1.0, 2.0)


def book_meeting(
    title: str,
    start_iso: str,
    duration_minutes: int,
    attendee_phone: str,
    customer_id: str,
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
            "location": row.get("location"),
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

    payload = {
        "customer_id": customer_id,
        "idempotency_key": idempotency_key,
        "start_iso": start_iso,
        "title": title,
        "rsvp_link": rsvp_link,
        "status": "confirmed",
        "location": location,
    }

    row = None
    for attempt, delay in enumerate((0, *CUSTOMER_FK_RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        try:
            row = get_client().table("meetings").insert(payload).execute().data[0]
            break
        except APIError as e:
            # meetings' only FK is customer_id -> customers, so the code alone
            # is enough to identify this (constraint name lives in e.message,
            # not e.details — checked against the real error shape below).
            if e.code != FK_VIOLATION or attempt == len(CUSTOMER_FK_RETRY_DELAYS):
                raise

    return {
        "id": row["id"],
        "title": row["title"],
        "start_iso": row["start_iso"],
        "duration_minutes": duration_minutes,
        "rsvp_link": row["rsvp_link"],
        "location": row.get("location"),
    }
