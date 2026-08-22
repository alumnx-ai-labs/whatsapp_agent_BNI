"""flow.py — the conversation state machine. CRM lookup, context retrieval,
customer registration, and calendar booking all go through app.agent.run_tool_call
(the LLM decides which LangChain tool to call and with what arguments). Pain-point
validation and time parsing use LangChain structured output — see
pain_point_agent.py and scheduling_agent.py.

Session state is loaded once at the top of handle_message and saved once at the
end — see session_store.py for why that ordering matters.
"""
import re

from app import context, pain_point_agent, scheduling_agent
from app.agent import run_tool_call
from app.session_store import State, Session, get_session, save_session, set_state

MAX_ELABORATION_ATTEMPTS = 3

OUR_OFFICE_ADDRESS = "Kondapur, Hyderabad"
OUR_OFFICE_MAPS_LINK = "https://maps.app.goo.gl/TNUaymUBpUS56N8p7"


async def handle_message(phone: str, text: str) -> str:
    session = get_session(phone)
    trimmed = (text or "").strip()

    if session.state == State.START:
        reply = await _handle_start(session, trimmed)
    elif session.state == State.AWAITING_NAME:
        reply = await _handle_name_capture(session, trimmed)
    # Pain-point discovery is disabled for now — new flow goes straight from
    # name/business capture to scheduling. See _handle_pain_point_submission
    # and _handle_meeting_willingness below (kept, unused) if this comes back.
    # elif session.state in (State.ASK_PAIN_POINT, State.AWAITING_ELABORATION):
    #     reply = await _handle_pain_point_submission(session, trimmed)
    # elif session.state == State.ASK_MEETING:
    #     reply = await _handle_meeting_willingness(session, trimmed)
    elif session.state == State.PROPOSE_TIME:
        reply = await _handle_availability_reply(session, trimmed)
    elif session.state == State.ASK_LOCATION:
        reply = await _handle_location_reply(session, trimmed)
    elif session.state == State.ASK_LOCATION_CONFIRM:
        reply = await _handle_location_confirm_reply(session, trimmed)
    elif session.state == State.ASK_LOCATION_DETAIL:
        reply = await _handle_location_detail_reply(session, trimmed)
    else:
        set_state(session, State.START)
        reply = await _handle_start(session, trimmed)

    save_session(session)
    return reply


async def _handle_start(session: Session, text: str = "") -> str:
    result = run_tool_call(f"Look up the customer with WhatsApp phone number {session.phone} in the CRM.")

    if not result.get("not_found"):
        session.customer = result
        set_state(session, State.PROPOSE_TIME)

        ctx = run_tool_call(f"Get the prior interaction context for customer_id {result['customer_id']}.")

        match = re.search(r"\b(hi|hello|hey)\b", text, re.IGNORECASE)
        greeting_word = match.group(1).capitalize() if match else "Hello"

        greeting = context.build_returning_greeting(result, None if ctx.get("not_found") else ctx, greeting_word=greeting_word)
        return f"{greeting}\n\nCould you share a good date and time to connect with you in person?"

    set_state(session, State.AWAITING_NAME)
    return "Hi. Looks like you've visited here for the first time.\n\nPlease share your name and business name."


async def _handle_name_capture(session: Session, text: str) -> str:
    parts = [p.strip() for p in re.split(r"[,\-]", text) if p.strip()]
    name = parts[0] if parts else text
    business_name = parts[1] if len(parts) > 1 else "their business"

    customer = run_tool_call(
        f"Register a new customer with phone number {session.phone}, name '{name}', business name '{business_name}'."
    )
    session.customer = customer
    set_state(session, State.PROPOSE_TIME)

    return f"Thanks, {name}! Could you share a good date and time to connect with you in person?"


# Pain-point discovery is disabled for now (new flow skips straight from
# name/business capture to scheduling) — kept here, unused, in case it comes back.
async def _handle_pain_point_submission(session: Session, text: str) -> str:
    session.pending_pain_point = text
    result = pain_point_agent.validate_pain_point(text)

    if not result["is_pain_point"] or not result["is_clear"]:
        session.elaboration_attempts += 1
        set_state(session, State.AWAITING_ELABORATION)

        if session.elaboration_attempts >= MAX_ELABORATION_ATTEMPTS:
            set_state(session, State.DONE)
            return "No worries — I'll flag this for one of our team to follow up with you directly instead. Thanks for your time!"

        return "Please elaborate — could you share a bit more detail on what's happening and which part of the business it affects?"

    session.validated_pain_point = {**result, "raw_text": text}
    set_state(session, State.ASK_MEETING)

    return (
        f"Got it — that sounds like a {result['category'].lower()} challenge ({result['subtopic']}). Thanks for sharing.\n\n"
        "Can you spare about 30 minutes to discuss this further and explore how we might help?"
    )


async def _handle_meeting_willingness(session: Session, text: str) -> str:
    affirmative = bool(re.search(r"\b(yes|sure|ok(ay)?|sounds good|works|yeah|yep)\b", text, re.I))

    if not affirmative:
        set_state(session, State.DONE)
        return "No problem at all — I've noted your pain point and someone from our team may reach out down the line. Thanks!"

    set_state(session, State.PROPOSE_TIME)
    return "Great! Help me with a good date and time for a quick 30-minute catchup to discuss how we can help solve your business pain point."


async def _handle_availability_reply(session: Session, text: str) -> str:
    # Accumulate across "could you be more specific" rounds — otherwise a date
    # given in one message ("29th aug") and a time given in the next ("5pm")
    # get parsed one at a time, and the second message alone (with no date in
    # it) silently overrides/loses the first instead of combining with it.
    combined_text = f"{session.pending_availability_text} {text}".strip()
    parsed = scheduling_agent.parse_availability(combined_text)

    if not parsed["parsed"] or parsed["needs_clarification"]:
        session.pending_availability_text = combined_text
        return 'Could you share a specific day and time (e.g. "Thursday 3pm")? I want to make sure I book the right slot.'

    session.pending_availability_text = ""
    session.proposed_time = parsed["iso"]
    session.proposed_time_human = parsed.get("human_readable")
    set_state(session, State.ASK_LOCATION)
    return "Great — and where would you like to meet? (e.g. your office, a cafe, or just a phone/video call)"


async def _handle_location_reply(session: Session, text: str) -> str:
    parsed = scheduling_agent.parse_location(text)
    return await _process_parsed_location(session, parsed)


async def _handle_location_confirm_reply(session: Session, text: str) -> str:
    affirmative = bool(re.search(r"\b(yes|sure|ok(ay)?|sounds good|works|yeah|yep|perfect|great)\b", text, re.I))

    if affirmative:
        return await _finalize_booking(session)

    # Not a "yes" — treat the reply as a different location instead.
    parsed = scheduling_agent.parse_location(text)
    return await _process_parsed_location(
        session, parsed, fallback_prompt='Where would you like to meet instead? (e.g. "Taj Hotel", or "phone call")'
    )


async def _process_parsed_location(session: Session, parsed: dict, fallback_prompt: str | None = None) -> str:
    if parsed["needs_clarification"] or not parsed["location"]:
        return fallback_prompt or 'Where would you like to meet? (e.g. "your office", "Taj Hotel", or "phone call")'

    # Clear any stale link from an earlier "our office" pass before deciding
    # again — otherwise switching to a different location later (e.g. after
    # rejecting our office in favor of an external venue) keeps showing our
    # office's maps link on a meeting that isn't at our office.
    session.proposed_location_link = None

    if parsed.get("is_our_office"):
        # They're asking about/proposing our own office — we have real
        # address info to share, so confirm it rather than booking blind.
        session.proposed_location = f"Our office, {OUR_OFFICE_ADDRESS}"
        session.proposed_location_link = OUR_OFFICE_MAPS_LINK
        set_state(session, State.ASK_LOCATION_CONFIRM)
        return (
            f"Sure, our office is located at {OUR_OFFICE_ADDRESS}. {OUR_OFFICE_MAPS_LINK}\n\n"
            "Does that work for you?"
        )

    session.proposed_location = parsed["location"]

    if parsed.get("is_remote"):
        # Phone/video call — no physical address to ask for.
        return await _finalize_booking(session)

    # An external physical venue (their office, a cafe, a named place) — ask
    # for enough detail to actually find it before locking it in.
    set_state(session, State.ASK_LOCATION_DETAIL)
    return f'Could you share the address, area, or a Google Maps link for {parsed["location"]}?'


async def _handle_location_detail_reply(session: Session, text: str) -> str:
    detail = text.strip()
    if detail:
        session.proposed_location = f"{session.proposed_location} ({detail})" if session.proposed_location else detail
    return await _finalize_booking(session)


async def _finalize_booking(session: Session) -> str:
    try:
        result = scheduling_agent.confirm_and_book(
            session.customer,
            session.proposed_time,
            session.proposed_time_human,
            location=session.proposed_location,
            location_link=session.proposed_location_link,
        )
    except Exception as e:  # noqa: BLE001
        # Don't let this bubble up to a raw 500 — that surfaces as "Sorry,
        # could you rephrase that?" from SkaleBot's own fallback, which reads
        # like the whole system is broken. State is left unchanged (not
        # DONE), so saying "yes" again retries this exact step.
        print(f"[flow] booking failed, asking customer to retry: {e}")
        return "Sorry, that took a moment too long on our end — could you say that once more to confirm?"

    set_state(session, State.DONE)
    return result["confirmation_text"]
