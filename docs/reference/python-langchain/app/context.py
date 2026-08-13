"""context.py — prior-interaction context for personalized greetings
(data/customer_context_history.json)."""
import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONTEXT_PATH = DATA_DIR / "customer_context_history.json"

_cache = None


def _load_context():
    global _cache
    if _cache is None:
        with open(CONTEXT_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def get_context_by_customer_id(customer_id: str) -> Optional[dict]:
    for c in _load_context():
        if c["customer_id"] == customer_id:
            return c
    return None


def build_returning_greeting(customer: dict, context: Optional[dict]) -> str:
    name = customer.get("contact_person") or "there"
    if not context:
        return f"Hello {name}! Good to hear from you again. How's everything going at {customer['business_name']}?"

    notes = context.get("personal_notes", {})
    topic = notes.get("small_talk_topic")
    location = notes.get("location")
    if topic:
        hook = f"How's {topic} treating you over in {location}?"
    else:
        hook = f"How are things going at {customer['business_name']}?"
    return f"Hello {name}! {hook}"
