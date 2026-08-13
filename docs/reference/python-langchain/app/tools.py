"""tools.py — LangChain @tool definitions wrapping the CRM and calendar functions.
These are genuine LangChain Tools: the LLM decides when and how to call them
(via bind_tools), rather than the application code calling crm/calendar directly.
Compare with the "direct" Python port, where crm.py and calendar_client.py are
called as plain functions with no LLM in the loop.
"""
from typing import Optional

from langchain_core.tools import tool

from app import crm_data, calendar_data


@tool
def lookup_customer(phone: str) -> dict:
    """Look up a customer in the CRM by their WhatsApp phone number.
    Returns the customer record (business_name, contact_person, sector, etc.)
    if found, or {"not_found": true} if this phone number has no CRM record."""
    record = crm_data.find_customer_by_phone(phone)
    return record or {"not_found": True}


@tool
def register_new_customer(phone: str, name: str, business_name: str) -> dict:
    """Register a brand-new customer in the CRM. Use this only when lookup_customer
    returned not_found for this phone number. Requires the customer's phone number,
    their name, and their business name."""
    return crm_data.register_new_customer(phone, name, business_name)


@tool
def book_calendar_meeting(business_name: str, phone: str, start_iso: str) -> dict:
    """Book a 30-minute discovery call on the calendar. start_iso must be a full
    ISO 8601 datetime (e.g. 2026-08-20T10:00:00+05:30). Returns the created event,
    including an RSVP link to send back to the customer."""
    return calendar_data.book_meeting(
        title=f"Meeting with {business_name}",
        start_iso=start_iso,
        duration_minutes=30,
        attendee_phone=phone,
    )


ALL_TOOLS = [lookup_customer, register_new_customer, book_calendar_meeting]
