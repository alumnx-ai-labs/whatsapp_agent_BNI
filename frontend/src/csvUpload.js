/** csvUpload.js — client-side CSV parsing for the bulk business-metadata
 * upload. No backend changes needed: each parsed row is submitted through
 * the existing single-customer POST /customers endpoint (api.js), one row
 * at a time, each with its own Idempotency-Key — so a re-upload of the same
 * file is exactly as safe as re-submitting the single-entry form (Backend 2's
 * upsert-on-phone behavior handles it).
 *
 * Expected header row (order doesn't matter, extra columns are ignored):
 *   business_name, phone_number, contact_person, address, sector, business_description
 * Only business_name and phone_number are required. See public/sample-customers.csv.
 */
import { normalizeText, sanitizePhoneDigits } from "./formValidation.js";

export const REQUIRED_HEADERS = ["business_name", "phone_number"];
export const KNOWN_HEADERS = [
  "business_name",
  "phone_number",
  "contact_person",
  "address",
  "sector",
  "business_description",
];

/** Minimal RFC4180-ish CSV parser: handles quoted fields with embedded
 * commas, escaped quotes (""), and \n/\r\n line endings. Good enough for
 * business-metadata exports without pulling in a dependency. */
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  const pushField = () => {
    row.push(field);
    field = "";
  };
  const pushRow = () => {
    pushField();
    rows.push(row);
    row = [];
  };

  for (let i = 0; i < text.length; i++) {
    const c = text[i];

    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
      continue;
    }

    if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      pushField();
    } else if (c === "\n") {
      pushRow();
    } else if (c === "\r") {
      // swallow — \r\n handled by the following \n; bare \r treated as line end
      if (text[i + 1] !== "\n") pushRow();
    } else {
      field += c;
    }
  }
  // last field/row if the file doesn't end with a newline
  if (field.length > 0 || row.length > 0) pushRow();

  // Drop fully-empty trailing rows (common with trailing newline in exports)
  return rows.filter((r) => r.some((cell) => cell.trim() !== ""));
}

/** Parses CSV text into an array of { business_name, phone_number, ... }
 * row objects keyed by the header row, plus 1-based line numbers for
 * error reporting. Throws if required headers are missing. */
export function parseCsvToRows(text) {
  const rawRows = parseCsv(text);
  if (rawRows.length === 0) {
    throw new Error("The file is empty.");
  }

  const headers = rawRows[0].map((h) => h.trim().toLowerCase());
  const missing = REQUIRED_HEADERS.filter((h) => !headers.includes(h));
  if (missing.length > 0) {
    throw new Error(`Missing required column(s): ${missing.join(", ")}. See the sample CSV for the expected format.`);
  }

  return rawRows.slice(1).map((cells, idx) => {
    const record = {};
    headers.forEach((header, colIdx) => {
      if (KNOWN_HEADERS.includes(header)) {
        record[header] = (cells[colIdx] ?? "").trim();
      }
    });
    return { lineNumber: idx + 2, record }; // +2: 1-based, plus the header row
  });
}

/** Same shape of check as formValidation.validateBeforeSubmit, adapted for
 * a raw CSV row (phone number here is a full string, not pre-split into
 * country code + local digits). */
export function validateCsvRow(record) {
  if (!record.business_name || !record.business_name.trim()) {
    return "business_name is required.";
  }
  const digits = sanitizePhoneDigits(record.phone_number);
  if (digits.length < 7) {
    return "phone_number must have at least 7 digits.";
  }
  return null;
}

/** Builds the same API payload shape as formValidation.buildSubmissionPayload.
 * Accepts phone numbers with or without a leading "+countrycode" — if none
 * is present, assumes +91 (matches the single-entry form's India default). */
export function buildPayloadFromCsvRow(record) {
  const rawPhone = (record.phone_number || "").trim();
  const hasCountryCode = rawPhone.trim().startsWith("+");
  const digits = sanitizePhoneDigits(rawPhone);
  const phone_number = hasCountryCode ? `+${digits}` : `+91 ${digits}`;

  return {
    business_name: normalizeText(record.business_name),
    phone_number,
    contact_person: normalizeText(record.contact_person) || null,
    address: normalizeText(record.address) || null,
    sector: normalizeText(record.sector) || null,
    business_description: normalizeText(record.business_description) || null,
  };
}
