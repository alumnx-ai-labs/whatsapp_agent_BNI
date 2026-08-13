// index.js — Express webhook server. This is the deployable entrypoint.
require('dotenv').config();
const express = require('express');
const whatsapp = require('./whatsappProvider');
const { handleMessage } = require('./flow');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true })); // Twilio sends form-encoded payloads

const PORT = process.env.PORT || 3000;

// Meta Cloud API webhook verification (GET) — required once when registering the webhook URL.
app.get('/webhook', (req, res) => {
  const mode = req.query['hub.mode'];
  const token = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];
  if (mode === 'subscribe' && token === process.env.META_WA_VERIFY_TOKEN) {
    return res.status(200).send(challenge);
  }
  return res.sendStatus(403);
});

// Inbound message webhook (all providers post here)
app.post('/webhook', async (req, res) => {
  try {
    const inbound = whatsapp.parseInbound(req);
    if (!inbound || !inbound.from) return res.sendStatus(200); // e.g. Meta status callbacks

    const replyText = await handleMessage(inbound.from, inbound.text);
    if (replyText) {
      await whatsapp.sendMessage(inbound.from, replyText);
    }
    res.sendStatus(200);
  } catch (err) {
    console.error('Error handling inbound message:', err);
    res.sendStatus(500);
  }
});

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
  console.log(`WhatsApp bot listening on :${PORT} (provider=${process.env.WHATSAPP_PROVIDER || 'console'})`);
});
