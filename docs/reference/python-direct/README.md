# WhatsApp Pain-Point Bot — Python (direct API, no framework)

1:1 Python port of the Node.js agent-code delivered earlier. Same state machine,
same behavior, same data files — just calling the Anthropic Python SDK directly
with no agent framework in between. Use this as the baseline to compare against
the LangChain version in `../python-langchain/`.

## Structure

```
app/
  main.py              FastAPI webhook server (deployable entrypoint)
  whatsapp_provider.py Provider abstraction: console (local testing) | twilio | meta
  flow.py              The conversation state machine — the core agent logic
  session.py           In-memory per-phone conversation state
  crm.py                Customer lookup against data/crm_mock_customers.csv
  context.py            Builds personalized greetings from data/customer_context_history.json
  pain_point_agent.py   Anthropic SDK call, rubric = data/pain_point_taxonomy.csv
  scheduling_agent.py   Anthropic SDK call for free-text time parsing + booking
  calendar_client.py    Calendar integration (stubbed; swap in Google Calendar API)
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

## Going live

Same as the Node version: set `WHATSAPP_PROVIDER=twilio` or `=meta`, fill in the
matching credentials in `.env`, deploy somewhere with a public HTTPS URL, and
point the provider's webhook at `/webhook`.
