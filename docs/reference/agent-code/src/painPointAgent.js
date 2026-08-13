// painPointAgent.js — LLM-based validation of a submitted business pain point
// against the taxonomy in data/pain_point_taxonomy.csv.
const fs = require('fs');
const path = require('path');
const { parse } = require('csv-parse/sync');
const Anthropic = require('@anthropic-ai/sdk');

const TAXONOMY_PATH = path.join(__dirname, '..', 'data', 'pain_point_taxonomy.csv');

let _taxonomyCache = null;
function loadTaxonomy() {
  if (_taxonomyCache) return _taxonomyCache;
  const raw = fs.readFileSync(TAXONOMY_PATH, 'utf-8');
  _taxonomyCache = parse(raw, { columns: true, skip_empty_lines: true, bom: true });
  return _taxonomyCache;
}

function taxonomyAsPromptBlock() {
  const rows = loadTaxonomy();
  const byCategory = {};
  for (const r of rows) {
    byCategory[r.category] = byCategory[r.category] || [];
    byCategory[r.category].push(`  - ${r.subtopic}: ${r.description} (keywords: ${r.example_phrases_keywords})`);
  }
  return Object.entries(byCategory)
    .map(([cat, subs]) => `${cat}:\n${subs.join('\n')}`)
    .join('\n\n');
}

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

/**
 * Validates a user's free-text message as a genuine, sufficiently detailed business pain point.
 * Returns { is_pain_point, is_clear, category, subtopic, reason }.
 */
async function validatePainPoint(userText) {
  const taxonomy = taxonomyAsPromptBlock();

  const system = `You are a validation agent for a business-pain-point intake bot. \
Given a customer's WhatsApp message, decide:
1) is_pain_point: does this describe a genuine business problem (operational, sales, marketing, financial, or support related)? \
General chit-chat, test messages, unrelated questions, or requests for pricing/support are NOT pain points.
2) is_clear: is there enough detail to act on (what's happening, roughly which area of the business)? \
A one-word or extremely vague statement is not clear even if it's on-topic.
3) If it is a pain point, classify it into the closest category and subtopic from this taxonomy:

${taxonomy}

Respond with ONLY valid JSON, no prose, in this exact shape:
{"is_pain_point": boolean, "is_clear": boolean, "category": string|null, "subtopic": string|null, "reason": string}`;

  const msg = await client.messages.create({
    model: 'claude-sonnet-5',
    max_tokens: 400,
    system,
    messages: [{ role: 'user', content: userText }],
  });

  const text = msg.content.map(b => (b.type === 'text' ? b.text : '')).join('');
  try {
    return JSON.parse(text);
  } catch (e) {
    // Fail safe: treat unparsable output as "needs elaboration" rather than crashing the flow.
    return { is_pain_point: false, is_clear: false, category: null, subtopic: null, reason: 'validator_parse_error' };
  }
}

module.exports = { validatePainPoint, loadTaxonomy };
