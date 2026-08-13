// flow.js — the conversation state machine. This is the "brain" wiring together
// CRM lookup, context-aware greeting, pain-point validation, and scheduling.
const { STATES, getSession, setState } = require('./session');
const { findCustomerByPhone, registerNewCustomer } = require('./crm');
const { getContextByCustomerId, buildReturningGreeting } = require('./context');
const { validatePainPoint } = require('./painPointAgent');
const { parseAvailability, confirmAndBook } = require('./schedulingAgent');

const MAX_ELABORATION_ATTEMPTS = 3;

// handleMessage is the single entrypoint the webhook calls for every inbound message.
// Returns the text the bot should send back.
async function handleMessage(phone, text) {
  const session = getSession(phone);
  const trimmed = (text || '').trim();

  // Entry trigger phrase from the QR code deep link
  if (session.state === STATES.START) {
    return handleStart(session, phone, trimmed);
  }

  switch (session.state) {
    case STATES.AWAITING_NAME:
      return handleNameCapture(session, trimmed);
    case STATES.ASK_PAIN_POINT:
    case STATES.AWAITING_ELABORATION:
      return handlePainPointSubmission(session, trimmed);
    case STATES.ASK_MEETING:
      return handleMeetingWillingness(session, trimmed);
    case STATES.PROPOSE_TIME:
      return handleAvailabilityReply(session, trimmed);
    default:
      // Conversation already completed — restart politely rather than erroring.
      setState(phone, STATES.START);
      return handleStart(session, phone, trimmed);
  }
}

async function handleStart(session, phone) {
  const customer = findCustomerByPhone(phone);

  if (customer) {
    session.customer = customer;
    const context = getContextByCustomerId(customer.customer_id);
    setState(phone, STATES.ASK_PAIN_POINT);
    const greeting = buildReturningGreeting(customer, context);
    return `${greeting}\n\nIs there any business pain point you have which we can address using AI? Please share the details.`;
  }

  setState(phone, STATES.AWAITING_NAME);
  return `Hi. Looks like you've visited here for the first time.\n\nPlease share your name and business name.`;
}

async function handleNameCapture(session, text) {
  // Very light parsing for the demo — expects "Name, Business" or "Name - Business".
  const parts = text.split(/[,\-]/).map(s => s.trim()).filter(Boolean);
  const name = parts[0] || text;
  const businessName = parts[1] || 'their business';

  const customer = registerNewCustomer({ phone: session.phone, name, businessName });
  session.customer = customer;
  setState(session.phone, STATES.ASK_PAIN_POINT);

  return `Thanks, ${name}! If there is any business pain point you have which we can address using AI, please let me know.`;
}

async function handlePainPointSubmission(session, text) {
  session.pendingPainPoint = text;
  const result = await validatePainPoint(text);

  if (!result.is_pain_point || !result.is_clear) {
    session.elaborationAttempts += 1;
    setState(session.phone, STATES.AWAITING_ELABORATION);

    if (session.elaborationAttempts >= MAX_ELABORATION_ATTEMPTS) {
      // Fallback: hand off to a human rather than loop forever.
      setState(session.phone, STATES.DONE);
      return `No worries — I'll flag this for one of our team to follow up with you directly instead. Thanks for your time!`;
    }
    return `Please elaborate — could you share a bit more detail on what's happening and which part of the business it affects?`;
  }

  session.validatedPainPoint = { ...result, raw_text: text };
  setState(session.phone, STATES.ASK_MEETING);

  return `Got it — that sounds like a ${result.category.toLowerCase()} challenge (${result.subtopic}). Thanks for sharing.\n\n` +
         `Can you spare about 30 minutes to discuss this further and explore how we might help?`;
}

async function handleMeetingWillingness(session, text) {
  const affirmative = /\b(yes|sure|ok(ay)?|sounds good|works|yeah|yep)\b/i.test(text);

  if (!affirmative) {
    setState(session.phone, STATES.DONE);
    return `No problem at all — I've noted your pain point and someone from our team may reach out down the line. Thanks!`;
  }

  setState(session.phone, STATES.PROPOSE_TIME);
  return `Great! Help me with a good date and time for a quick 30-minute catchup to discuss how we can help solve your business pain point.`;
}

async function handleAvailabilityReply(session, text) {
  const parsed = await parseAvailability(text);

  if (!parsed.parsed || parsed.needs_clarification) {
    return `Could you share a specific day and time (e.g. "Thursday 3pm")? I want to make sure I book the right slot.`;
  }

  const { confirmationText } = await confirmAndBook({
    customer: session.customer,
    iso: parsed.iso,
    humanReadable: parsed.human_readable,
  });

  setState(session.phone, STATES.DONE);
  return confirmationText;
}

module.exports = { handleMessage };
