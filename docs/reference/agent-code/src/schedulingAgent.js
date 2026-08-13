// schedulingAgent.js — parses free-text availability into a normalized date/time,
// and books the meeting via the (stubbed) calendar module.
const Anthropic = require('@anthropic-ai/sdk');
const { bookMeeting } = require('./calendar');

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

/**
 * Parses free text like "Tuesday afternoon" or "anytime after 3pm Thursday" into a
 * candidate ISO datetime. Returns { parsed: boolean, iso: string|null, needs_clarification: boolean }.
 */
async function parseAvailability(userText, { nowIso } = {}) {
  const now = nowIso || new Date().toISOString();
  const system = `You extract a single proposed meeting date/time from a WhatsApp message about scheduling. \
Assume the current timestamp is ${now} and IST timezone unless the user states otherwise. \
The meeting is a 30-minute call. If the message is too vague to produce a specific date and time \
(e.g. just "sometime next week"), set needs_clarification to true instead of guessing.
Respond with ONLY JSON: {"parsed": boolean, "iso": string|null, "needs_clarification": boolean, "human_readable": string|null}`;

  const msg = await client.messages.create({
    model: 'claude-sonnet-5',
    max_tokens: 200,
    system,
    messages: [{ role: 'user', content: userText }],
  });

  const text = msg.content.map(b => (b.type === 'text' ? b.text : '')).join('');
  try {
    return JSON.parse(text);
  } catch {
    return { parsed: false, iso: null, needs_clarification: true, human_readable: null };
  }
}

async function confirmAndBook({ customer, iso, humanReadable }) {
  const event = await bookMeeting({
    title: `Meeting with ${customer.business_name}`,
    startIso: iso,
    durationMinutes: 30,
    attendeePhone: customer.phone_number,
  });
  return {
    confirmationText:
      `Meeting confirmed: ${humanReadable || iso}\n` +
      `${event.title}\n` +
      `View details and RSVP: ${event.rsvpLink}`,
    event,
  };
}

module.exports = { parseAvailability, confirmAndBook };
