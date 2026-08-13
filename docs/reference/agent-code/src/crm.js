// crm.js — customer lookup against the mock CRM CSV (data/crm_mock_customers.csv)
const fs = require('fs');
const path = require('path');
const { parse } = require('csv-parse/sync');

const CRM_PATH = path.join(__dirname, '..', 'data', 'crm_mock_customers.csv');

let _cache = null;
function loadCrm() {
  if (_cache) return _cache;
  const raw = fs.readFileSync(CRM_PATH, 'utf-8');
  _cache = parse(raw, { columns: true, skip_empty_lines: true, bom: true });
  return _cache;
}

function normalizePhone(p) {
  return (p || '').replace(/[^\d]/g, '').replace(/^91/, ''); // strip non-digits and leading country code
}

// Look up a customer by WhatsApp sender number. Returns null if not found (new user).
function findCustomerByPhone(phone) {
  const target = normalizePhone(phone);
  const rows = loadCrm();
  return rows.find(r => normalizePhone(r.phone_number) === target) || null;
}

function registerNewCustomer({ phone, name, businessName }) {
  // In production this would INSERT into the real CRM/database.
  // Stubbed here — log intent, return a synthetic record for the rest of the flow to use.
  console.log(`[crm] would create new record: ${name} / ${businessName} / ${phone}`);
  return {
    customer_id: `NEW_${Date.now()}`,
    business_name: businessName,
    phone_number: phone,
    contact_person: name,
    sector: 'unclassified',
    business_description: '',
  };
}

module.exports = { findCustomerByPhone, registerNewCustomer, normalizePhone };
