"""flow.py — same state machine shape as the direct port, but the CRM lookup and
new-customer registration steps go through app.agent.run_tool_call (an LLM deciding
which LangChain tool to call and with what arguments) instead of calling crm_data
functions directly. Pain-point validation and scheduling also route through
LangChain (structured output / tool-calling) — see pain_point_agent.py and
scheduling_agent.py for details.
"""
import re

from app import context, pain_point_agent, scheduling_agent
from app.agent import run_tool_call
from app.session import State, get_session, set_state

MAX_ELABORATION_ATTEMPTS = 3


async def handle_message(phone: str, text: str) -> str:
    session = get_session(phone)
    trimmed = (text or "").strip()

    if session.state == State.START:
        return await _handle_start(session, phone)

    if session.state == State.AWAITING_NAME:
        return await _handle_name_capture(session, trimmed)
    if session.state in (State.ASK_PAIN_POINT, State.AWAITING_ELABORATION):
        return await _handle_pain_point_submission(session, trimmed)
    if session.state == State.ASK_MEETING:
        return await _handle_meeting_willingness(session, trimmed)
    if session.state == State.PROPOSE_TIME:
        return await _handle_availability_reply(session, trimmed)

    set_state(phone, State.START)
    return await _handle_start(session, phone)


async def _handle_start(session, phone: str) -> str:
    # Routed through the LangChain tool-calling agent instead of calling crm_data directly.
    result = run_tool_call(f"Look up the customer with WhatsApp phone number {phone} in the CRM.")

    if not result.get("not_found"):
        session.customer = result
        ctx = context.get_context_by_customer_id(result["customer_id"])
        set_state(phone, State.ASK_PAIN_POINT)
        greeting = context.build_returning_greeting(result, ctx)
        return f"{greeting}\n\nIs there any business pain point you have which we can address using AI? Please share the details."

    set_state(phone, State.AWAITING_NAME)
    return "Hi. Looks like you've visited here for the first time.\n\nPlease share your name and business name."


async def _handle_name_capture(session, text: str) -> str:
    parts = [p.strip() for p in re.split(r"[,\-]", text) if p.strip()]
    name = parts[0] if parts else text
    business_name = parts[1] if len(parts) > 1 else "their business"

    customer = run_tool_call(
        f"Register a new customer with phone number {session.phone}, name '{name}', business name '{business_name}'."
    )
    session.customer = customer
    set_state(session.phone, State.ASK_PAIN_POINT)

    return f"Thanks, {name}! If there is any business pain point you have which we can address using AI, please let me know."


async def _handle_pain_point_submission(session, text: str) -> str:
    session.pending_pain_point = text
    result = pain_point_agent.validate_pain_point(text)

    if not result["is_pain_point"] or not result["is_clear"]:
        session.elaboration_attempts += 1
        set_state(session.phone, State.AWAITING_ELABORATION)

        if session.elaboration_attempts >= MAX_ELABORATION_ATTEMPTS:
            set_state(session.phone, State.DONE)
            return "No worries — I'll flag this for one of our team to follow up with you directly instead. Thanks for your time!"

        return "Please elaborate — could you share a bit more detail on what's happening and which part of the business it affects?"

    session.validated_pain_point = {**result, "raw_text": text}
    set_state(session.phone, State.ASK_MEETING)

    return (
        f"Got it — that sounds like a {result['category'].lower()} challenge ({result['subtopic']}). Thanks for sharing.\n\n"
        "Can you spare about 30 minutes to discuss this further and explore how we might help?"
    )


async def _handle_meeting_willingness(session, text: str) -> str:
    affirmative = bool(re.search(r"\b(yes|sure|ok(ay)?|sounds good|works|yeah|yep)\b", text, re.I))

    if not affirmative:
        set_state(session.phone, State.DONE)
        return "No problem at all — I've noted your pain point and someone from our team may reach out down the line. Thanks!"

    set_state(session.phone, State.PROPOSE_TIME)
    return "Great! Help me with a good date and time for a quick 30-minute catchup to discuss how we can help solve your business pain point."


async def _handle_availability_reply(session, text: str) -> str:
    parsed = scheduling_agent.parse_availability(text)

    if not parsed["parsed"] or parsed["needs_clarification"]:
        return 'Could you share a specific day and time (e.g. "Thursday 3pm")? I want to make sure I book the right slot.'

    result = scheduling_agent.confirm_and_book(session.customer, parsed["iso"], parsed.get("human_readable"))
    set_state(session.phone, State.DONE)
    return result["confirmation_text"]
