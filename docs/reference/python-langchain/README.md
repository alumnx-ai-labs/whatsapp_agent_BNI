# WhatsApp Pain-Point Bot — Python (LangChain, tool-calling)

Same flow and same behavior as `../python-direct/`, but the CRM and calendar
actions are implemented as real LangChain `@tool` functions, bound to a
`ChatAnthropic` model that decides which tool to call and extracts the
arguments itself — rather than the application code calling `crm.py` /
`calendar_client.py` directly.

## What's different from the direct-API version

| Step | Direct version | This version |
|---|---|---|
| CRM lookup | `crm.find_customer_by_phone(phone)` — plain function call | `agent.run_tool_call(...)` — LLM picks `lookup_customer` tool, extracts `phone` arg, tool executes |
| New customer registration | `crm.register_new_customer(...)` — plain function call | LLM picks `register_new_customer` tool, extracts phone/name/business from a natural-language instruction |
| Calendar booking | `calendar_client.book_meeting(...)` — plain function call | LLM picks `book_calendar_meeting` tool, extracts business/phone/iso args |
| Pain-point validation | Raw Anthropic SDK call, manually parse JSON | `ChatAnthropic.with_structured_output(PainPointValidation)` — a Pydantic-schema-constrained call, which Anthropic implements as forced tool-calling under the hood |
| Availability parsing | Raw Anthropic SDK call, manually parse JSON | `ChatAnthropic.with_structured_output(AvailabilityParse)` |

`app/tools.py` holds the three explicit `@tool` definitions. `app/agent.py` binds
them to the model (`model.bind_tools(...)`) and runs a single-call tool-execution
loop: ask the model to satisfy an instruction, read `ai_msg.tool_calls`, execute
the matching tool, return its result. `app/flow.py` calls `run_tool_call(...)`
with natural-language instructions instead of calling CRM/calendar functions
directly — that's the actual behavioral difference from the direct-API version.

## Structure

```
app/
  main.py                FastAPI webhook server (same as direct version)
  whatsapp_provider.py    Provider abstraction (same as direct version)
  flow.py                 State machine — CRM/calendar steps routed through the agent
  session.py               In-memory per-phone conversation state (same as direct version)
  tools.py                 LangChain @tool definitions: lookup_customer, register_new_customer, book_calendar_meeting
  agent.py                  Binds tools to ChatAnthropic, executes whichever tool the model calls
  crm_data.py               Underlying CRM data access (wrapped by the lookup_customer / register_new_customer tools)
  calendar_data.py          Underlying calendar data access (wrapped by the book_calendar_meeting tool)
  context.py                 Personalized greeting builder (same as direct version, no LLM involved)
  pain_point_agent.py        LangChain structured-output validator, rubric = data/pain_point_taxonomy.csv
  scheduling_agent.py        LangChain structured-output time parser + tool-routed booking
data/
  crm_mock_customers.csv
  customer_context_history.json
  pain_point_taxonomy.csv
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in ANTHROPIC_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Test locally without WhatsApp (WHATSAPP_PROVIDER=console by default):

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"from": "+919526018159", "text": "Hello Oscar"}'
```

## Why keep the deterministic state machine instead of a fully autonomous agent?

A fully autonomous LangGraph/AgentExecutor loop (where the LLM decides the next
conversational step, not just which tool to call for a given step) is possible,
but trades away predictability: you'd lose the guarantee that "elaborate" always
loops back to the same question, or that the flow always follows QR-scan → lookup
→ pain point → acknowledge → schedule in that order. This version is a middle
ground for the assignment: the *flow* stays deterministic and matches the
original diagram exactly, while the *actions within each step* (CRM/calendar) go
through genuine LangChain tool-calling, and the *reasoning steps* (validation,
time parsing) use LangChain's structured-output mechanism. If your course wants
the fully autonomous version instead, say so and I'll build a LangGraph variant.

## Going live

Same as the other versions: set `WHATSAPP_PROVIDER=twilio` or `=meta`, fill in
credentials, deploy with a public HTTPS URL, point the webhook at `/webhook`.
