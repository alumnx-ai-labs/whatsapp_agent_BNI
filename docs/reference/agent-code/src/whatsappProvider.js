// whatsappProvider.js — abstraction over the WhatsApp channel so the flow logic
// doesn't care whether messages arrive via Twilio, Meta Cloud API, or local console testing.
//
// To go live: set WHATSAPP_PROVIDER=twilio or =meta in .env and fill in the matching
// credentials. Each provider must implement:
//   - parseInbound(req): (expressRequest) => { from: string, text: string }
//   - sendMessage(to, text): (string, string) => Promise<void>

const PROVIDER = process.env.WHATSAPP_PROVIDER || 'console';

const consoleProvider = {
  parseInbound(req) {
    // For local testing: POST { "from": "+919876543210", "text": "Hello Oscar" }
    return { from: req.body.from, text: req.body.text };
  },
  async sendMessage(to, text) {
    console.log(`\n[WhatsApp -> ${to}]\n${text}\n`);
  },
};

const twilioProvider = {
  parseInbound(req) {
    // Twilio webhook sends application/x-www-form-urlencoded with "From" and "Body"
    return { from: (req.body.From || '').replace('whatsapp:', ''), text: req.body.Body };
  },
  async sendMessage(to, text) {
    const twilio = require('twilio')(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);
    await twilio.messages.create({
      from: process.env.TWILIO_WHATSAPP_FROM,
      to: `whatsapp:${to}`,
      body: text,
    });
  },
};

const metaProvider = {
  parseInbound(req) {
    // Meta Cloud API webhook payload shape
    const entry = req.body.entry?.[0];
    const change = entry?.changes?.[0];
    const message = change?.value?.messages?.[0];
    if (!message) return null;
    return { from: message.from, text: message.text?.body || '' };
  },
  async sendMessage(to, text) {
    const url = `https://graph.facebook.com/v20.0/${process.env.META_WA_PHONE_NUMBER_ID}/messages`;
    await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.META_WA_ACCESS_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messaging_product: 'whatsapp',
        to,
        type: 'text',
        text: { body: text },
      }),
    });
  },
};

const providers = { console: consoleProvider, twilio: twilioProvider, meta: metaProvider };

module.exports = providers[PROVIDER] || consoleProvider;
