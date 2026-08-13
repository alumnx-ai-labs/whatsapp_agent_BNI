# WhatsApp Pain-Point Bot — Backend (Supabase + FastAPI + LangChain/Gemini)

Updated per spec:

- **Backend:** PostgreSQL via Supabase, Python, FastAPI.
- **Agent:** LangChain, multiple tools, Gemini 3.1 Flash-Lite as the LLM.
- **Idempotency:** inbound WhatsApp messages, customer registration, and meeting
  booking are all idempotent (see below); the companion React frontend (`../frontend/`)
  is idempotent on submission too.

This replaces the CSV/JSON-file version delivered earlier. The conversation flow
and behavior are unchanged — same states, same transitions — only the data layer
and LLM provider changed.

## Architecture

```
app/
  main.py               FastAPI app: POST /webhook (WhatsApp), POST /customers (frontend), /health
  flow.py                Conversation state machine
  session_store.py         Conversation state persisted to Supabase (conversation_sessions table)
  agent.py                  Binds tools.py to Gemini via LangChain, executes tool calls
  tools.py                   4 LangChain @tool functions: lookup_customer, register_new_customer,
                               get_customer_context, book_calendar_meeting
  pain_point_agent.py          LangChain structured-output validator (Gemini), rubric = pain_point_taxonomy table
  scheduling_agent.py            LangChain structured-output time parser (Gemini) + tool-routed booking
  crm_lookup.py                    Supabase-backed customer lookup by phone (Owner: Backend 1)
  crm_registration.py              Supabase-backed new-customer registration + metadata upsert (Owner: Backend 2)
  phone_utils.py                   Shared phone normalization used by both crm_ modules above
  context.py                       Supabase-backed prior-interaction context + greeting builder (Owner: Backend 3)
  calendar_data.py                  Supabase-backed meeting booking (idempotent), stubbed calendar provider (Owner: Backend 4)
  idempotency.py                     Inbound-message dedupe + generic API idempotency-key cache
  whatsapp_provider.py                Twilio / Meta / console abstraction, extracts provider message_id
  db.py                                 Supabase client
db/
  schema.sql             Run this in Supabase before anything else
  seed.py                 Loads the mock CRM/context/taxonomy data into Supabase
data/
  crm_mock_customers.csv, customer_context_history.json, pain_point_taxonomy.csv
  (source files for db/seed.py — the app itself reads from Supabase, not these)
```

## Setup

1. Create a Supabase project. In the SQL editor, run `db/schema.sql`.
2. Get a Gemini API key from Google AI Studio.
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fill in `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GOOGLE_API_KEY`.
5. `python db/seed.py` — loads the mock data into your Supabase tables.
6. `uvicorn app.main:app --reload --port 8000`

Test locally without WhatsApp:

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"from": "+919526018159", "text": "Hello Oscar"}'
```

## Idempotency — what's covered and how

| Scenario | Mechanism |
|---|---|
| WhatsApp provider retries a webhook delivery (timeout/5xx) | `processed_messages` table, keyed on the provider's message id (Twilio `MessageSid` / Meta `id`). Checked in `main.py` before the message reaches the flow at all. |
| Same customer's registration step runs twice (e.g. a retried message reprocesses `AWAITING_NAME`) | `crm_data.register_new_customer` checks for an existing record by `normalized_phone` first; also upserts on that column as a second layer against races. |
| The scheduling step books the same slot twice (e.g. `PROPOSE_TIME` re-entered) | `calendar_data.book_meeting` keys each booking on `f"{customer_id}:{start_iso}"` (unique constraint in `meetings`); a repeat call returns the existing event instead of creating a new one. |
| FastAPI restarts / redeploys mid-conversation, or scales to multiple workers | Session state lives in Postgres (`conversation_sessions`), not an in-process dict — any worker can pick up the next message correctly. |
| React frontend's metadata upload is retried after a network error | Client-generated `Idempotency-Key` header, cached server-side in `api_idempotency_keys`; also upserts on `normalized_phone` regardless. See `../frontend/README.md`. |

## Why Gemini 3.1 Flash-Lite

Set via `GEMINI_MODEL` env var (defaults to `gemini-3.1-flash-lite`) — cheap and
fast, appropriate for the two high-frequency, low-complexity LLM calls in this
flow (pain-point classification against a fixed taxonomy, and short free-text
date/time extraction). Swap the env var if your course wants a heavier model for
comparison; no code changes needed.

## Multiple tools (LangChain agent requirement)

`app/tools.py` defines four `@tool` functions bound to the Gemini model in
`app/agent.py`: `lookup_customer`, `register_new_customer`, `get_customer_context`,
`book_calendar_meeting`. `flow.py` drives the state machine deterministically (so
the conversation always follows the same order as the original flowchart) but
delegates every CRM/calendar action to the model via `agent.run_tool_call(...)` —
the LLM picks which of the four tools to call and extracts the arguments from a
natural-language instruction each time.

## Known gaps / what I couldn't verify without live credentials

- Never connected to a real Supabase project or Google AI Studio key — the flow
  logic is verified against a fake in-memory Supabase client and mocked Gemini
  responses (matches the same scenarios tested in the earlier CSV-based version,
  plus explicit checks for each idempotency guarantee above). Run `db/seed.py`
  and a real end-to-end webhook call once you have credentials to confirm.
- Row-level security (RLS) policies aren't defined in `schema.sql` — the backend
  uses the Supabase service-role key, which bypasses RLS entirely. If you expose
  any table to the frontend directly (not recommended — go through FastAPI), add
  RLS policies first.
