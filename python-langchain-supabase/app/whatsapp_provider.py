"""whatsapp_provider.py — abstraction over the WhatsApp channel. Each provider
also extracts a message_id used for inbound-message idempotency (see
app/idempotency.py) — Twilio/Meta retry webhook delivery on timeout/5xx, and
without a dedupe check the same message would be run through the state machine
twice.
"""
import os
from typing import Optional

import httpx
from fastapi import Request


class InboundMessage:
    def __init__(self, from_: str, text: str, message_id: Optional[str] = None):
        self.from_ = from_
        self.text = text
        self.message_id = message_id


async def _console_parse_inbound(request: Request) -> Optional[InboundMessage]:
    body = await request.json()
    # Local testing: pass "message_id" explicitly to test idempotency, or omit
    # it to always process (idempotency.mark_message_processed treats a
    # missing id as "always process").
    return InboundMessage(from_=body.get("from"), text=body.get("text"), message_id=body.get("message_id"))


async def _console_send_message(to: str, text: str) -> None:
    print(f"\n[WhatsApp -> {to}]\n{text}\n")


async def _twilio_parse_inbound(request: Request) -> Optional[InboundMessage]:
    form = await request.form()
    from_ = (form.get("From") or "").replace("whatsapp:", "")
    return InboundMessage(from_=from_, text=form.get("Body"), message_id=form.get("MessageSid"))


async def _twilio_send_message(to: str, text: str) -> None:
    from twilio.rest import Client

    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        to=f"whatsapp:{to}",
        body=text,
    )


async def _meta_parse_inbound(request: Request) -> Optional[InboundMessage]:
    body = await request.json()
    entry = (body.get("entry") or [{}])[0]
    change = (entry.get("changes") or [{}])[0]
    message = (change.get("value", {}).get("messages") or [None])[0]
    if not message:
        return None
    return InboundMessage(
        from_=message.get("from"),
        text=message.get("text", {}).get("body", ""),
        message_id=message.get("id"),
    )


async def _meta_send_message(to: str, text: str) -> None:
    url = f"https://graph.facebook.com/v20.0/{os.environ['META_WA_PHONE_NUMBER_ID']}/messages"
    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            headers={"Authorization": f"Bearer {os.environ['META_WA_ACCESS_TOKEN']}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
        )


_PROVIDERS = {
    "console": (_console_parse_inbound, _console_send_message),
    "twilio": (_twilio_parse_inbound, _twilio_send_message),
    "meta": (_meta_parse_inbound, _meta_send_message),
}


def get_provider():
    name = os.environ.get("WHATSAPP_PROVIDER", "console")
    parse_inbound, send_message = _PROVIDERS.get(name, _PROVIDERS["console"])
    return parse_inbound, send_message
