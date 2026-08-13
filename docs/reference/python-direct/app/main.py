"""main.py — FastAPI webhook server. This is the deployable entrypoint."""
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response

load_dotenv()

from app.flow import handle_message  # noqa: E402  (import after load_dotenv)
from app.whatsapp_provider import get_provider  # noqa: E402

app = FastAPI(title="WhatsApp Pain-Point Discovery Bot")


@app.get("/webhook")
async def verify_webhook(request: Request):
    # Meta Cloud API webhook verification handshake
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

    try:
        reply_text = await handle_message(inbound.from_, inbound.text)
        if reply_text:
            await send_message(inbound.from_, reply_text)
    except Exception as e:  # noqa: BLE001
        print(f"Error handling inbound message: {e}")
        return Response(status_code=500)

    return Response(status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok"}
