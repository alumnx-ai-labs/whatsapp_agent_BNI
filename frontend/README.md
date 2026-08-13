# Business Metadata Frontend

Small React (Vite) app for uploading business metadata into the CRM the
WhatsApp bot reads from. Submits to the FastAPI backend's `POST /customers`
endpoint (see `../python-langchain/app/main.py`).

## Idempotency

Every form submission generates a UUID `Idempotency-Key` (see `src/api.js`)
that's sent as a request header and reused across automatic retries of the
*same* submission. The backend caches the response per key (`api_idempotency_keys`
table), so a retried request after a network blip returns the original result
instead of re-processing. A fresh key is only minted when the user explicitly
starts a new submission ("Add another business").

Separately, the backend also upserts on the customer's normalized phone number,
so even without the Idempotency-Key mechanism, re-submitting the same business's
metadata updates the existing CRM record rather than creating a duplicate.

## Setup

```bash
npm install
cp .env.example .env
# set VITE_API_BASE to wherever the FastAPI backend is running
npm run dev
```
