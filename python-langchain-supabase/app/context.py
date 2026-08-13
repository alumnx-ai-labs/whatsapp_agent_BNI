"""context.py — prior-interaction context for personalized greetings, now read
from the Supabase `customer_context` table instead of a local JSON file.
"""
from app.db import get_client


def get_context_by_customer_id(customer_id: str) -> dict | None:
    resp = (
        get_client()
        .table("customer_context")
        .select("*")
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def build_returning_greeting(customer: dict, context: dict | None) -> str:
    name = customer.get("contact_person") or "there"
    if not context:
        return f"Hello {name}! Good to hear from you again. How's everything going at {customer['business_name']}?"

    notes = context.get("personal_notes") or {}
    topic = notes.get("small_talk_topic")
    location = notes.get("location")
    if topic:
        hook = f"How's {topic} treating you over in {location}?"
    else:
        hook = f"How are things going at {customer['business_name']}?"
    return f"Hello {name}! {hook}"
