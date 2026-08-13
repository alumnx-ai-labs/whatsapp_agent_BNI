"""scheduling_agent.py — LangChain version. Availability parsing uses structured
output (implicit tool call); the actual booking goes through the explicit
book_calendar_meeting tool via agent.run_tool_call, so the LLM both extracts the
time AND is the one invoking the calendar tool with its own extracted arguments.
"""
import os
from datetime import datetime, timezone
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
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
        model = ChatAnthropic(model="claude-sonnet-5", api_key=os.environ.get("ANTHROPIC_API_KEY"))
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
    # This step routes through the LangChain tool (book_calendar_meeting) via the
    # tool-calling agent, rather than calling calendar_data.book_meeting directly.
    instruction = (
        f"Book a calendar meeting for business '{customer['business_name']}', "
        f"phone {customer['phone_number']}, starting at {iso}."
    )
    event = run_tool_call(instruction)
    confirmation_text = (
        f"Meeting confirmed: {human_readable or iso}\n"
        f"{event['title']}\n"
        f"View details and RSVP: {event['rsvp_link']}"
    )
    return {"confirmation_text": confirmation_text, "event": event}
