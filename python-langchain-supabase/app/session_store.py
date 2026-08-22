"""session_store.py — conversation state persisted to the Supabase
`conversation_sessions` table (replaces the earlier in-memory dict).

Why persist this: an in-memory dict is per-process. The moment you run more
than one FastAPI worker (or redeploy mid-conversation), a user's next message
could land on a process that has never heard of them, silently resetting the
flow. Persisting to Postgres makes the bot durable and horizontally scalable.

Usage pattern: call get_session(phone) ONCE per inbound message at the top of
flow.handle_message, mutate the returned Session object as the flow proceeds,
then call save_session(session) once at the end. Do not call get_session()
again mid-request for the same phone — that would silently discard in-memory
mutations made earlier in the same request.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.db import get_client


class State(str, Enum):
    START = "START"
    AWAITING_NAME = "AWAITING_NAME"
    ASK_PAIN_POINT = "ASK_PAIN_POINT"
    AWAITING_ELABORATION = "AWAITING_ELABORATION"
    ASK_MEETING = "ASK_MEETING"
    PROPOSE_TIME = "PROPOSE_TIME"
    ASK_LOCATION = "ASK_LOCATION"
    ASK_LOCATION_CONFIRM = "ASK_LOCATION_CONFIRM"
    ASK_LOCATION_DETAIL = "ASK_LOCATION_DETAIL"
    CONFIRM_TIME = "CONFIRM_TIME"
    DONE = "DONE"


@dataclass
class Session:
    phone: str
    state: State = State.START
    elaboration_attempts: int = 0
    customer: Optional[dict] = None
    pending_pain_point: Optional[str] = None
    validated_pain_point: Optional[dict] = None
    proposed_time: Optional[str] = None
    proposed_time_human: Optional[str] = None
    proposed_location: Optional[str] = None
    # A maps link, kept separate from proposed_location — it's only ever shown
    # in the final user-facing confirmation, never fed into the natural-language
    # instruction sent to the LLM tool-call (a raw URL embedded there confused
    # its argument extraction, mangling customer_id in testing).
    proposed_location_link: Optional[str] = None
    # Raw text accumulated across "could you be more specific" rounds, so a
    # date given in one message ("29th aug") and a time given in the next
    # ("5pm") get parsed together instead of the second message alone
    # silently overriding/losing the first.
    pending_availability_text: str = ""


def get_session(phone: str) -> Session:
    resp = (
        get_client()
        .table("conversation_sessions")
        .select("*")
        .eq("phone_number", phone)
        .limit(1)
        .execute()
    )
    if resp.data:
        row = resp.data[0]
        return Session(
            phone=phone,
            state=State(row["state"]),
            elaboration_attempts=row["elaboration_attempts"],
            customer=row.get("customer_snapshot"),  # full cached record, not just the id
            pending_pain_point=row.get("pending_pain_point"),
            validated_pain_point=row.get("validated_pain_point"),
            proposed_time=row.get("proposed_time"),
            proposed_time_human=row.get("proposed_time_human"),
            proposed_location=row.get("proposed_location"),
            proposed_location_link=row.get("proposed_location_link"),
            pending_availability_text=row.get("pending_availability_text") or "",
        )

    # Idempotent create: upsert rather than plain insert, in case two inbound
    # messages for a brand-new phone number race each other.
    get_client().table("conversation_sessions").upsert(
        {"phone_number": phone, "state": State.START.value, "elaboration_attempts": 0},
        on_conflict="phone_number",
    ).execute()
    return Session(phone=phone)


def save_session(session: Session) -> None:
    get_client().table("conversation_sessions").upsert(
        {
            "phone_number": session.phone,
            "state": session.state.value,
            "elaboration_attempts": session.elaboration_attempts,
            "customer_id": (session.customer or {}).get("customer_id"),
            "customer_snapshot": session.customer,
            "pending_pain_point": session.pending_pain_point,
            "validated_pain_point": session.validated_pain_point,
            "proposed_time": session.proposed_time,
            "proposed_time_human": session.proposed_time_human,
            "proposed_location": session.proposed_location,
            "proposed_location_link": session.proposed_location_link,
            "pending_availability_text": session.pending_availability_text,
        },
        on_conflict="phone_number",
    ).execute()


def set_state(session: Session, state: State) -> None:
    session.state = state


def has_active_session(phone: str) -> bool:
    """True if this phone already has a pain-point-bot conversation in
    progress. Deliberately does NOT call get_session() — that upserts a
    fresh row for any phone it's asked about, which would wrongly mark
    every phone that's ever been checked (e.g. unrelated alumni traffic
    sharing this WhatsApp number) as "ours" from then on. This is a plain
    read with no side effect."""
    resp = (
        get_client()
        .table("conversation_sessions")
        .select("state")
        .eq("phone_number", phone)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return False
    return resp.data[0]["state"] != State.DONE.value
