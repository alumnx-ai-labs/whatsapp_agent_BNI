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


class AvailabilityParse(BaseModel):
    parsed: bool = Field(description="Whether a specific date/time could be extracted")
    iso: Optional[str] = Field(default=None, description="Proposed meeting start as ISO 8601")
    needs_clarification: bool = Field(description="True if the message was too vague to act on")
    human_readable: Optional[str] = Field(default=None, description="Friendly rendering of the proposed time")


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


def confirm_and_book(customer: dict, iso: str, human_readable: str | None) -> dict:
    business_name = customer.get("business_name") or ""
    instruction = (
        f"Book a calendar meeting for business '{business_name}', "
        f"phone {customer['phone_number']}, customer_id {customer['customer_id']}, "
        f"starting at {iso}."
    )
    event = run_tool_call(instruction)

    date_time_str = human_readable or iso
    business_label = f" with {business_name}" if business_name and business_name.lower() != "their business" else ""

    confirmation_text = (
        "✅ *Meeting Confirmed!*\n\n"
        f"📅 *Date & Time:* {date_time_str}\n"
        f"💼 *Meeting:* Discovery Call{business_label}\n"
        f"⏳ *Duration:* 30 Minutes\n"
        f"📍 *Location:* Virtual (Google Meet / WhatsApp Call)\n\n"
        f"🔗 *RSVP & Calendar Invite:* {event['rsvp_link']}\n\n"
        "Looking forward to speaking with you!"
    )
    return {"confirmation_text": confirmation_text, "event": event}
