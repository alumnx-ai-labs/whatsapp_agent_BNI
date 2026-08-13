"""tools.py — LangChain @tool definitions wrapping the CRM and calendar (Supabase-backed).
These are genuine LangChain Tools: the LLM decides when and how to call them
(via bind_tools), rather than the application code calling crm_lookup/crm_registration/
calendar_data directly.
"""
from langchain_core.tools import tool

from app import calendar_data, context, crm_lookup, crm_registration


@tool
def lookup_customer(phone: str) -> dict:
    """Look up a customer in the CRM by their WhatsApp phone number.
    Returns the customer record (business_name, contact_person, sector, etc.)
    if found, or {"not_found": true} if this phone number has no CRM record."""
    record = crm_lookup.find_customer_by_phone(phone)
    return record or {"not_found": True}


@tool
def register_new_customer(phone: str, name: str, business_name: str) -> dict:
    """Register a brand-new customer in the CRM. Use this only when lookup_customer
    returned not_found for this phone number. Requires the customer's phone number,
    their name, and their business name. Idempotent — calling this twice for the
    same phone number returns the existing record rather than creating a duplicate."""
    return crm_registration.register_new_customer(phone, name, business_name)


@tool
def get_customer_context(customer_id: str) -> dict:
    """Retrieve prior-interaction context for a customer_id — relationship stage,
    past pain points raised, and personalization notes (location, small-talk topic)
    used to build a warm, specific greeting for returning customers."""
    ctx = context.get_context_by_customer_id(customer_id)
    return ctx or {"not_found": True}


@tool
def book_calendar_meeting(business_name: str, phone: str, customer_id: str, start_iso: str) -> dict:
    """Book a 30-minute discovery call on the calendar. start_iso must be a full
    ISO 8601 datetime (e.g. 2026-08-20T10:00:00+05:30). Idempotent — calling this
    twice for the same customer_id and start_iso returns the same booked event
    instead of creating a duplicate meeting. Returns the created event, including
    an RSVP link to send back to the customer."""
    return calendar_data.book_meeting(
        title=f"Meeting with {business_name}",
        start_iso=start_iso,
        duration_minutes=30,
        attendee_phone=phone,
        customer_id=customer_id,
    )


ALL_TOOLS = [lookup_customer, register_new_customer, get_customer_context, book_calendar_meeting]
