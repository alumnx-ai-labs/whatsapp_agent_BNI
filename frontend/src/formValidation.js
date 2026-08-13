/** Common dial codes for the phone field dropdown (default: India +91). */
export const COUNTRY_CODES = [
  { code: "IN", name: "India", dialCode: "+91", flag: "🇮🇳" },
  { code: "US", name: "United States", dialCode: "+1", flag: "🇺🇸" },
  { code: "GB", name: "United Kingdom", dialCode: "+44", flag: "🇬🇧" },
  { code: "AE", name: "United Arab Emirates", dialCode: "+971", flag: "🇦🇪" },
  { code: "SG", name: "Singapore", dialCode: "+65", flag: "🇸🇬" },
  { code: "AU", name: "Australia", dialCode: "+61", flag: "🇦🇺" },
  { code: "CA", name: "Canada", dialCode: "+1", flag: "🇨🇦" },
  { code: "DE", name: "Germany", dialCode: "+49", flag: "🇩🇪" },
  { code: "FR", name: "France", dialCode: "+33", flag: "🇫🇷" },
  { code: "SA", name: "Saudi Arabia", dialCode: "+966", flag: "🇸🇦" },
  { code: "QA", name: "Qatar", dialCode: "+974", flag: "🇶🇦" },
  { code: "MY", name: "Malaysia", dialCode: "+60", flag: "🇲🇾" },
  { code: "NZ", name: "New Zealand", dialCode: "+64", flag: "🇳🇿" },
  { code: "JP", name: "Japan", dialCode: "+81", flag: "🇯🇵" },
  { code: "CN", name: "China", dialCode: "+86", flag: "🇨🇳" },
  { code: "ZA", name: "South Africa", dialCode: "+27", flag: "🇿🇦" },
  { code: "BR", name: "Brazil", dialCode: "+55", flag: "🇧🇷" },
  { code: "MX", name: "Mexico", dialCode: "+52", flag: "🇲🇽" },
  { code: "IT", name: "Italy", dialCode: "+39", flag: "🇮🇹" },
  { code: "ES", name: "Spain", dialCode: "+34", flag: "🇪🇸" },
  { code: "NL", name: "Netherlands", dialCode: "+31", flag: "🇳🇱" },
  { code: "CH", name: "Switzerland", dialCode: "+41", flag: "🇨🇭" },
  { code: "SE", name: "Sweden", dialCode: "+46", flag: "🇸🇪" },
  { code: "NO", name: "Norway", dialCode: "+47", flag: "🇳🇴" },
  { code: "DK", name: "Denmark", dialCode: "+45", flag: "🇩🇰" },
  { code: "FI", name: "Finland", dialCode: "+358", flag: "🇫🇮" },
  { code: "IE", name: "Ireland", dialCode: "+353", flag: "🇮🇪" },
  { code: "PT", name: "Portugal", dialCode: "+351", flag: "🇵🇹" },
  { code: "BE", name: "Belgium", dialCode: "+32", flag: "🇧🇪" },
  { code: "AT", name: "Austria", dialCode: "+43", flag: "🇦🇹" },
  { code: "PL", name: "Poland", dialCode: "+48", flag: "🇵🇱" },
  { code: "TR", name: "Turkey", dialCode: "+90", flag: "🇹🇷" },
  { code: "EG", name: "Egypt", dialCode: "+20", flag: "🇪🇬" },
  { code: "NG", name: "Nigeria", dialCode: "+234", flag: "🇳🇬" },
  { code: "KE", name: "Kenya", dialCode: "+254", flag: "🇰🇪" },
  { code: "PK", name: "Pakistan", dialCode: "+92", flag: "🇵🇰" },
  { code: "BD", name: "Bangladesh", dialCode: "+880", flag: "🇧🇩" },
  { code: "LK", name: "Sri Lanka", dialCode: "+94", flag: "🇱🇰" },
  { code: "NP", name: "Nepal", dialCode: "+977", flag: "🇳🇵" },
  { code: "ID", name: "Indonesia", dialCode: "+62", flag: "🇮🇩" },
  { code: "PH", name: "Philippines", dialCode: "+63", flag: "🇵🇭" },
  { code: "TH", name: "Thailand", dialCode: "+66", flag: "🇹🇭" },
  { code: "VN", name: "Vietnam", dialCode: "+84", flag: "🇻🇳" },
  { code: "KR", name: "South Korea", dialCode: "+82", flag: "🇰🇷" },
  { code: "HK", name: "Hong Kong", dialCode: "+852", flag: "🇭🇰" },
];

export const DEFAULT_COUNTRY_CODE = "IN";

export function getDialCodeForCountry(countryCode) {
  const country = COUNTRY_CODES.find((c) => c.code === countryCode);
  return country?.dialCode ?? "+91";
}

/** Trim and collapse internal whitespace for text fields. */
export function normalizeText(value) {
  if (value == null || typeof value !== "string") return "";
  return value.trim().replace(/\s+/g, " ");
}

/** Strip everything except digits from a phone input. */
export function sanitizePhoneDigits(value) {
  if (value == null) return "";
  return String(value).replace(/\D/g, "");
}

/**
 * Format phone for the backend UPSERT endpoint.
 * Matches CRM style: "+91 9876543210" (dial code + space + local digits).
 */
export function formatPhoneForApi(dialCode, localDigits) {
  const code = dialCode.startsWith("+") ? dialCode : `+${dialCode}`;
  return `${code} ${sanitizePhoneDigits(localDigits)}`;
}

const LETTER_PATTERN = /[a-zA-Z\u00C0-\u024F\u0900-\u097F]/;

/**
 * Reject pure numbers, decimals, dot-only, or symbol-only contact names.
 * Empty values are allowed (optional field).
 */
export function isInvalidContactPerson(value) {
  if (!value || !value.trim()) return false;

  const trimmed = value.trim();

  if (/^\d+$/.test(trimmed)) return true;
  if (/^\d*\.\d+$/.test(trimmed)) return true;
  if (/^\.+$/.test(trimmed)) return true;
  if (/^[\d.\s]+$/.test(trimmed) && /\./.test(trimmed)) return true;
  if (!LETTER_PATTERN.test(trimmed) && /[^\s]/.test(trimmed)) return true;

  return false;
}

/** Return an error message if required fields fail trim-based checks, else null. */
export function validateBeforeSubmit(form, phoneLocalDigits) {
  if (!form.business_name.trim()) {
    return "Business name is required.";
  }
  if (phoneLocalDigits.length < 7) {
    return "Enter a valid phone number (at least 7 digits).";
  }
  return null;
}

/** Build the API payload with normalized text fields and formatted phone. */
export function buildSubmissionPayload(form, countryCode, phoneLocalDigits) {
  const contactPerson = normalizeText(form.contact_person);
  const address = normalizeText(form.address);
  const businessDescription = normalizeText(form.business_description);

  return {
    business_name: normalizeText(form.business_name),
    phone_number: formatPhoneForApi(getDialCodeForCountry(countryCode), phoneLocalDigits),
    contact_person: contactPerson || null,
    address: address || null,
    sector: form.sector || null,
    business_description: businessDescription || null,
  };
}
