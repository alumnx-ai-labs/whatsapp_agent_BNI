"""scheduling_agent.py — LangChain structured-output time parsing (Gemini), plus
tool-routed booking: the LLM extracts the time, then agent.run_tool_call has the
model itself invoke book_calendar_meeting with those extracted arguments.
"""
import os
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent import run_tool_call

_structured_model = None
_location_model = None


class AvailabilityParse(BaseModel):
    parsed: bool = Field(description="Whether a specific date/time could be extracted")
    iso: Optional[str] = Field(default=None, description="Proposed meeting start as ISO 8601")
    needs_clarification: bool = Field(description="True if the message was too vague to act on")
    human_readable: Optional[str] = Field(default=None, description="Friendly rendering of the proposed time")


class LocationParse(BaseModel):
    location: Optional[str] = Field(
        default=None,
        description="A short, clean description of the meeting location, normalized from the "
        "user's reply (e.g. 'can I meet at your office?' -> 'our office', 'maybe Taj Hotel "
        "works' -> 'Taj Hotel', 'let's just do a call' -> 'phone call').",
    )
    needs_clarification: bool = Field(
        description="True if the reply doesn't specify or imply any location at all "
        "(e.g. 'not sure', 'what do you suggest?')."
    )
    is_our_office: bool = Field(
        description="True if the reply is asking about, proposing, or agreeing to meet at OUR "
        "own office/place (e.g. 'can we meet at your office?', 'your office works', 'sure, your "
        "place') rather than naming an external venue (a hotel, a cafe, their own office, etc.)."
    )
    is_remote: bool = Field(
        description="True if this is a phone or video call — not a physical place, so no "
        "address/area/maps link should ever be requested for it."
    )


def _get_structured_model():
    global _structured_model
    if _structured_model is None:
        model = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=0,
        )
        _structured_model = model.with_structured_output(AvailabilityParse)
    return _structured_model


def _get_location_model():
    global _location_model
    if _location_model is None:
        model = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=0,
        )
        _location_model = model.with_structured_output(LocationParse)
    return _location_model


def parse_availability(user_text: str, now_iso: str | None = None) -> dict:
    now = now_iso or datetime.now(timezone.utc).isoformat()
    system = f"""You extract a single proposed meeting date/time from a WhatsApp message about scheduling. \
Assume the current timestamp is {now} and IST timezone unless the user states otherwise. \
The meeting is a 30-minute call. If the message is too vague to produce a specific date and time \
(e.g. just "sometime next week"), set needs_clarification to true instead of guessing."""

    result: AvailabilityParse = _get_structured_model().invoke(
        [SystemMessage(content=system), HumanMessage(content=user_text)]
    )
    return result.model_dump()


def parse_location(user_text: str) -> dict:
    system = """You extract a clean, short meeting location from a WhatsApp reply to "where would \
you like to meet?" — normalize conversational phrasing (a question, a suggestion, filler words) into \
a plain location description rather than echoing the raw text back. If the reply doesn't specify or \
imply a location at all, set needs_clarification to true instead of guessing. Separately, flag \
is_our_office when the reply is about meeting at OUR office rather than naming an external venue, \
and flag is_remote when it's a phone/video call rather than a physical place."""

    result: LocationParse = _get_location_model().invoke(
        [SystemMessage(content=system), HumanMessage(content=user_text)]
    )
    return result.model_dump()


def confirm_and_book(
    customer: dict,
    iso: str,
    human_readable: str | None,
    location: str | None = None,
    location_link: str | None = None,
) -> dict:
    # location_link is deliberately NOT included here — a raw URL embedded in
    # this natural-language instruction confused the LLM's argument
    # extraction in testing (mangled customer_id). It's only ever shown in
    # the final confirmation_text below, never sent to the tool-call.
    instruction = (
        f"Book a calendar meeting for business '{customer['business_name']}', "
        f"phone {customer['phone_number']}, customer_id {customer['customer_id']}, "
        f"starting at {iso}"
        + (f", meeting location: {location}." if location else ".")
    )
    event = run_tool_call(instruction)

    business_name = customer.get("business_name") or ""
    business_label = f" with {business_name}" if business_name and business_name.lower() != "their business" else ""
    location_block = f"{location}\n{location_link}" if location and location_link else location
    confirmation_text = (
        "✅ *Meeting Confirmed!*\n\n"
        f"📅 *Date & Time:* {human_readable or iso}\n"
        f"💼 *Meeting:* Discovery Call{business_label}\n"
        f"⏳ *Duration:* {event['duration_minutes']} minutes\n"
        + (f"📍 *Location:* {location_block}\n\n" if location else "\n")
        + "Looking forward to speaking with you!"
    )
    return {"confirmation_text": confirmation_text, "event": event}
