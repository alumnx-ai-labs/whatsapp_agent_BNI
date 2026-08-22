"""main.py — FastAPI app. Three entrypoints:
  POST /webhook       inbound WhatsApp messages, fire-and-forget style
                       (Twilio/Meta/console — reply sent via a separate
                       outbound API call, see whatsapp_provider.py)
  POST /webhook-sync  inbound WhatsApp messages, synchronous request/response
                       style (for relays — e.g. the Alumnx Node backend's
                       SkaleBot "AI agent" webhook — that expect the reply
                       text back in THIS response, not a separate send call)
  POST /customers     business metadata upload from the React frontend
                       (idempotent)
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from app import crm_registration, idempotency, session_store  # noqa: E402
from app.flow import handle_message  # noqa: E402
from app.whatsapp_provider import get_provider  # noqa: E402

# The literal phrase the QR code pre-fills into WhatsApp ("Hello Oscar")
# to start a brand-new pain-point conversation. Case-insensitive, trimmed.
PAIN_POINT_TRIGGER_PHRASE = "hello oscar"

app = FastAPI(title="WhatsApp Pain-Point Discovery Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WhatsApp webhook ────────────────────────────────────────────

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == os.environ.get("META_WA_VERIFY_TOKEN"):
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def inbound_webhook(request: Request):
    parse_inbound, send_message = get_provider()
    inbound = await parse_inbound(request)
    if not inbound or not inbound.from_:
        return Response(status_code=200)

    if not idempotency.mark_message_processed(inbound.message_id, inbound.from_):
        # Duplicate delivery of a message we've already processed (provider
        # retry) — acknowledge without re-running the flow.
        return Response(status_code=200)

    try:
        reply_text = await handle_message(inbound.from_, inbound.text)
        if reply_text:
            await send_message(inbound.from_, reply_text)
    except Exception as e:  # noqa: BLE001
        print(f"Error handling inbound message: {e}")
        return Response(status_code=500)

    return Response(status_code=200)


# ── Synchronous webhook (for relays, e.g. Alumnx's Node backend) ─

class SyncWebhookIn(BaseModel):
    phone: str
    text: str
    message_id: str | None = None


@app.post("/webhook-sync")
async def inbound_webhook_sync(payload: SyncWebhookIn):
    # This WhatsApp number is shared with other bots (e.g. the alumni
    # job-search bot) behind the same relay. Only claim a message as ours
    # if it's the QR code's trigger phrase (a brand-new pain-point
    # conversation) or this phone already has one in progress — otherwise
    # tell the caller to fall through to its own (e.g. alumni) logic.
    # TEMPORARY: echo mode. Claims EVERY message on this shared number and
    # replies with the exact same text — used to test whether the Node
    # relay's synchronous response actually gets delivered to WhatsApp at
    # all, independent of ticket state or trigger-phrase matching. Unset
    # ECHO_MODE (or delete this block) to restore the real is_ours gating.
    if os.environ.get("ECHO_MODE", "").lower() == "true":
        return {"handled": True, "reply": payload.text or "(empty message)"}

    trimmed_text = (payload.text or "").strip().lower()
    is_ours = (
        trimmed_text == PAIN_POINT_TRIGGER_PHRASE
        or "oscar" in trimmed_text
        or session_store.has_active_session(payload.phone)
    )
    if not is_ours:
        return {"handled": False}

    # TEMPORARY: end-to-end wiring smoke test. Once the Node relay is
    # confirmed reaching this endpoint over real WhatsApp/SkaleBot, unset
    # HELLO_WORLD_TEST_MODE (or delete this block) to restore the real flow.
    # Still gated by is_ours above, so unrelated (e.g. alumni) traffic on
    # this shared number is never affected either way.
    if os.environ.get("HELLO_WORLD_TEST_MODE", "").lower() == "true":
        return {"handled": True, "reply": "Hello World"}

    # Same idempotency-key cache already used by POST /customers — reused
    # here keyed on message_id, so a retried relay call (e.g. the caller
    # timed out waiting and tries again) replays the same reply instead of
    # re-running the flow (which could otherwise double-advance state or
    # double-book a meeting).
    cached = idempotency.get_cached_response(payload.message_id)
    if cached is not None:
        return cached

    try:
        reply_text = await handle_message(payload.phone, payload.text)
    except Exception as e:  # noqa: BLE001
        print(f"Error handling inbound sync message: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    result = {"handled": True, "reply": reply_text or ""}
    idempotency.store_cached_response(payload.message_id, result)
    return result


# ── Business metadata upload (React frontend) ───────────────────

class CustomerMetadataIn(BaseModel):
    business_name: str
    phone_number: str
    address: str | None = None
    contact_person: str | None = None
    sector: str | None = None
    business_description: str | None = None


@app.post("/customers")
async def upsert_customer_metadata(payload: CustomerMetadataIn, request: Request):
    idempotency_key = request.headers.get("Idempotency-Key")

    cached = idempotency.get_cached_response(idempotency_key)
    if cached is not None:
        return cached

    try:
        customer = crm_registration.upsert_customer_metadata(payload.model_dump())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e

    idempotency.store_cached_response(idempotency_key, customer)
    return customer

# ── Bookings (React frontend) ────────────────────────────────────

@app.get("/bookings")
async def get_confirmed_bookings(status: str = "confirmed"):
    """
    Fetches bookings from Supabase filtered by status (default: 'confirmed').
    """
    try:
        from app.db import get_client
        supabase = get_client()
        
        # Queries the 'bookings' table for confirmed records ordered by newest first
        response = (
            supabase.table("meetings")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Database fetch failed: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── TEMPORARY: wiring diagnostic ─────────────────────────────────
# Records that *something* called this, regardless of payload shape.
# Used to confirm whether the Node relay's pain-point check is even
# being reached at all, without needing log access to that service.
# Safe to delete once the SkaleBot wiring is confirmed working.

@app.post("/debug-ping")
async def debug_ping(request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {"raw": (await request.body()).decode("utf-8", errors="replace")}
    from app.db import get_client
    get_client().table("debug_pings").insert({"source": "node-relay", "payload": body}).execute()
    return {}
