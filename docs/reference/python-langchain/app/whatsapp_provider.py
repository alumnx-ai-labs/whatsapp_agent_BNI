"""whatsapp_provider.py — abstraction over the WhatsApp channel so flow.py doesn't
care whether messages arrive via Twilio, Meta Cloud API, or local console testing.

To go live: set WHATSAPP_PROVIDER=twilio or =meta in .env and fill in the matching
credentials.
"""
import os
from typing import Optional

import httpx
from fastapi import Request


class InboundMessage:
    def __init__(self, from_: str, text: str):
        self.from_ = from_
        self.text = text


async def _console_parse_inbound(request: Request) -> Optional[InboundMessage]:
    body = await request.json()
    return InboundMessage(from_=body.get("from"), text=body.get("text"))


async def _console_send_message(to: str, text: str) -> None:
    print(f"\n[WhatsApp -> {to}]\n{text}\n")


async def _twilio_parse_inbound(request: Request) -> Optional[InboundMessage]:
    form = await request.form()
    from_ = (form.get("From") or "").replace("whatsapp:", "")
    return InboundMessage(from_=from_, text=form.get("Body"))


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
    return InboundMessage(from_=message.get("from"), text=message.get("text", {}).get("body", ""))


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
