"""scheduling_agent.py — parses free-text availability into a normalized date/time,
and books the meeting via the (stubbed) calendar module. Direct Anthropic SDK call.
"""
import json
import os
from datetime import datetime, timezone

import anthropic

from app.calendar_client import book_meeting

_client = None


def _client_instance():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def parse_availability(user_text: str, now_iso: str | None = None) -> dict:
    now = now_iso or datetime.now(timezone.utc).isoformat()
    system = f"""You extract a single proposed meeting date/time from a WhatsApp message about scheduling. \
Assume the current timestamp is {now} and IST timezone unless the user states otherwise. \
The meeting is a 30-minute call. If the message is too vague to produce a specific date and time \
(e.g. just "sometime next week"), set needs_clarification to true instead of guessing.
Respond with ONLY JSON: {{"parsed": boolean, "iso": string|null, "needs_clarification": boolean, "human_readable": string|null}}"""

    msg = _client_instance().messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parsed": False, "iso": None, "needs_clarification": True, "human_readable": None}


def confirm_and_book(customer: dict, iso: str, human_readable: str | None) -> dict:
    event = book_meeting(
        title=f"Meeting with {customer['business_name']}",
        start_iso=iso,
        duration_minutes=30,
        attendee_phone=customer["phone_number"],
    )
    confirmation_text = (
        f"Meeting confirmed: {human_readable or iso}\n"
        f"{event['title']}\n"
        f"View details and RSVP: {event['rsvp_link']}"
    )
    return {"confirmation_text": confirmation_text, "event": event}
