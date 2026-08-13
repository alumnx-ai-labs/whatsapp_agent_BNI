"""session.py — in-memory per-phone-number conversation state.
Swap for Redis/DB in production; the state machine only needs get/set/clear.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class State(str, Enum):
    START = "START"
    AWAITING_NAME = "AWAITING_NAME"
    ASK_PAIN_POINT = "ASK_PAIN_POINT"
    AWAITING_ELABORATION = "AWAITING_ELABORATION"
    ASK_MEETING = "ASK_MEETING"
    PROPOSE_TIME = "PROPOSE_TIME"
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


_sessions: dict[str, Session] = {}


def get_session(phone: str) -> Session:
    if phone not in _sessions:
        _sessions[phone] = Session(phone=phone)
    return _sessions[phone]


def set_state(phone: str, state: State) -> None:
    get_session(phone).state = state


def reset_session(phone: str) -> None:
    _sessions.pop(phone, None)
