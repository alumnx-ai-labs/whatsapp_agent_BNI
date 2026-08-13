"""calendar_client.py — calendar integration, stubbed for local testing.
Swap this out for the real Google Calendar API (or Outlook) once credentials are available.
"""
import os
import random
import string


def book_meeting(title: str, start_iso: str, duration_minutes: int, attendee_phone: str) -> dict:
    provider = os.environ.get("CALENDAR_PROVIDER", "stub")

    if provider == "stub":
        fake_id = "evt_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        print(f"[calendar:stub] booking \"{title}\" at {start_iso} for {duration_minutes}min (attendee {attendee_phone})")
        return {
            "id": fake_id,
            "title": title,
            "start_iso": start_iso,
            "duration_minutes": duration_minutes,
            "rsvp_link": f"https://calendar.app.google/{fake_id}",
        }

    # --- Real Google Calendar integration goes here ---
    # from googleapiclient.discovery import build
    # service = build("calendar", "v3", credentials=creds)
    # event = service.events().insert(calendarId="primary", body={...}).execute()
    # return {"id": event["id"], "title": title, "start_iso": start_iso,
    #         "duration_minutes": duration_minutes, "rsvp_link": event["htmlLink"]}
    raise NotImplementedError(f"CALENDAR_PROVIDER={provider} not implemented yet")
