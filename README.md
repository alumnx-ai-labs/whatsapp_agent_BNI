# WhatsApp Pain-Point Discovery Bot

A WhatsApp bot ("Oscar") that turns a QR-code scan into a qualified lead:
look up the sender in the CRM (greet returning customers personally,
onboard new ones), ask about a business pain point, validate it against a
fixed taxonomy with an LLM, then schedule and book a 30-minute discovery
call.

Full spec, the original flow diagrams, and reference data are in
[`docs/`](docs/).

## Live stack

- [`python-langchain-supabase/`](python-langchain-supabase/) — FastAPI +
  LangChain + Gemini + Supabase (Postgres). This is the version the team is
  building on. It implements the flow as a deterministic state machine
  (`app/flow.py`) that delegates every CRM/calendar action to an LLM-driven
  LangChain tool call (`app/agent.py` + `app/tools.py`), and is idempotent
  end-to-end (webhook retries, duplicate registration, duplicate booking —
  see its README for details).
- [`frontend/`](frontend/) — React (Vite) app for uploading/maintaining the
  business metadata the bot's CRM reads from (`POST /customers`).

Three earlier reference implementations (Node.js direct, Python direct,
Python+LangChain without Supabase) are archived, not maintained, under
[`docs/reference/`](docs/reference/) for comparison only. **Do not build
against them.**

## Module ownership

See [`CODEOWNERS`](CODEOWNERS) for the current file → owner mapping, and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the fork/branch/PR workflow.

| Module | Files | Wraps into |
|---|---|---|
| Frontend upload UI | `frontend/` | `POST /customers` |
| CRM lookup | `python-langchain-supabase/app/crm_lookup.py` | `tools.lookup_customer` |
| Customer registration | `python-langchain-supabase/app/crm_registration.py` | `tools.register_new_customer` |
| Prior-interaction context | `python-langchain-supabase/app/context.py` | `tools.get_customer_context` |
| Calendar booking | `python-langchain-supabase/app/calendar_data.py` | `tools.book_calendar_meeting` |
| Orchestration (lead) | `app/agent.py`, `app/flow.py`, `app/main.py`, `app/db.py`, `db/schema.sql`, `app/session_store.py`, `app/idempotency.py`, `app/whatsapp_provider.py`, `app/pain_point_agent.py`, `app/scheduling_agent.py` | glue + integration |

## Setup

See [`python-langchain-supabase/README.md`](python-langchain-supabase/README.md)
and [`frontend/README.md`](frontend/README.md).
