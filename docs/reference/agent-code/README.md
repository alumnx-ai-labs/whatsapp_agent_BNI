# WhatsApp Pain-Point Discovery Bot — Agent Code

Reference implementation of the flow: QR-triggered WhatsApp entry -> CRM lookup ->
context-aware greeting for returning users -> pain-point capture -> AI validation
against a 5-category taxonomy -> acknowledgment -> meeting scheduling -> calendar booking.

This is provider-agnostic. As written it runs fully locally against `WHATSAPP_PROVIDER=console`
(no real WhatsApp account needed) so you can test the logic end-to-end. Swap in Twilio or
Meta Cloud API credentials when you're ready to go live — no changes to `src/flow.js` needed.

## Structure

```
src/
  index.js            Express webhook server (deployable entrypoint)
  whatsappProvider.js  Provider abstraction: console (local testing) | twilio | meta
  flow.js              The conversation state machine — the core agent logic
  session.js           In-memory per-phone conversation state (swap for Redis/DB in prod)
  crm.js               Customer lookup against data/crm_mock_customers.csv
  context.js           Builds personalized greetings from data/customer_context_history.json
  painPointAgent.js    Claude-based validator, rubric = data/pain_point_taxonomy.csv
  schedulingAgent.js   Claude-based free-text time parser + booking orchestration
  calendar.js          Calendar integration (stubbed; swap in Google Calendar API)
data/
  crm_mock_customers.csv           (copied from your CRM file)
  customer_context_history.json    (copied from your context file)
  pain_point_taxonomy.csv          (copied from your taxonomy file)
```

## Setup

```bash
npm install
cp .env.example .env
# fill in ANTHROPIC_API_KEY at minimum — required for the validation/scheduling agents
```

## Test locally without a real WhatsApp account

With `WHATSAPP_PROVIDER=console` (the default), inbound messages are just POSTed to the
webhook directly and replies print to the console instead of being sent over WhatsApp:

```bash
npm start
# in another terminal:
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{"from": "+919526018159", "text": "Hello Oscar"}'
```

The included test in this delivery (`test_flow.js`, not part of the shipped package —
ask me to re-add it if useful) exercises the full state machine with mocked LLM responses
so you can verify logic without spending API calls.

## Going live on WhatsApp

You need a WhatsApp Business API account through one of:

- **Twilio** (fastest to prototype — free sandbox available): set `WHATSAPP_PROVIDER=twilio`,
  fill in `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WHATSAPP_FROM`, then point your
  Twilio WhatsApp sandbox webhook at `https://<your-host>/webhook`.
- **Meta WhatsApp Cloud API** (official, needs Meta Business verification): set
  `WHATSAPP_PROVIDER=meta`, fill in `META_WA_PHONE_NUMBER_ID` / `META_WA_ACCESS_TOKEN` /
  `META_WA_VERIFY_TOKEN`, register the webhook URL (`GET /webhook` handles the verification
  handshake already).
- **Gupshup** or similar BSPs: implement a third provider object in `whatsappProvider.js`
  following the same `{ parseInbound, sendMessage }` shape.

You also need to host this somewhere reachable from the internet (Render, Railway, a small
VM, etc.) — WhatsApp providers require an HTTPS webhook URL, they won't call `localhost`.
For local testing before you deploy, tools like `ngrok` can expose your dev server temporarily.

## What's stubbed vs. real

| Piece | Status |
|---|---|
| CRM lookup | Real, reads your actual CSV |
| Context-aware greeting | Real, reads your actual JSON |
| Pain-point validation | Real LLM call (Claude), rubric = your taxonomy CSV |
| Scheduling / time parsing | Real LLM call (Claude) |
| Calendar booking | Stubbed — logs and returns a fake RSVP link; swap in Google Calendar API in `calendar.js` |
| WhatsApp send/receive | Real for Twilio/Meta once credentials are added; `console` mode for local testing |
| Session storage | In-memory (resets on restart) — fine for a demo, swap for Redis/DB for production |

## Known simplifications (worth calling out in your assignment writeup)

- New-user name/business capture uses naive comma-split parsing (`"Name, Business"`); a
  production version would likely use an LLM extraction step here too.
- No conversation timeout / re-engagement logic if a user goes silent mid-flow.
- No de-duplication if the same customer raises multiple pain points in one session.
- Elaboration loop caps at 3 attempts before falling back to a human-handoff message.
