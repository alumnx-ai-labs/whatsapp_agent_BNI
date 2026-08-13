// context.js — prior-interaction context for personalized greetings (data/customer_context_history.json)
const fs = require('fs');
const path = require('path');

const CONTEXT_PATH = path.join(__dirname, '..', 'data', 'customer_context_history.json');

let _cache = null;
function loadContext() {
  if (_cache) return _cache;
  _cache = JSON.parse(fs.readFileSync(CONTEXT_PATH, 'utf-8'));
  return _cache;
}

function getContextByCustomerId(customerId) {
  return loadContext().find(c => c.customer_id === customerId) || null;
}

// Builds a personalized greeting string for a returning user using their stored context.
// Falls back to a generic-but-warm greeting if no context is on file.
function buildReturningGreeting(customer, context) {
  const name = customer.contact_person || 'there';
  if (!context) {
    return `Hello ${name}! Good to hear from you again. How's everything going at ${customer.business_name}?`;
  }
  const { small_talk_topic, location } = context.personal_notes || {};
  const hook = small_talk_topic
    ? `How's ${small_talk_topic} treating you over in ${location}?`
    : `How are things going at ${customer.business_name}?`;
  return `Hello ${name}! ${hook}`;
}

module.exports = { getContextByCustomerId, buildReturningGreeting, loadContext };
