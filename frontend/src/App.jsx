import { useEffect, useRef, useState } from "react";
import { newIdempotencyKey, submitBusinessMetadata } from "./api.js";
import BookingsList from "./BookingsList.jsx";
import {
  buildSubmissionPayload,
  COUNTRY_CODES,
  DEFAULT_COUNTRY_CODE,
  isInvalidContactPerson,
  sanitizePhoneDigits,
  validateBeforeSubmit,
} from "./formValidation.js";
import { buildPayloadFromCsvRow, parseCsvToRows, validateCsvRow } from "./csvUpload.js";

const SECTORS = [
  "Retail",
  "Food & Beverage",
  "Manufacturing",
  "Logistics",
  "Professional Services",
  "Hospitality",
  "Healthcare / Wellness",
  "Education",
  "Real Estate",
  "Other",
];

const EMPTY_FORM = {
  business_name: "",
  address: "",
  contact_person: "",
  sector: "",
  business_description: "",
};

export default function App() {
  const [activeTab, setActiveTab] = useState("upload"); // "upload" | "bookings"
  const [mode, setMode] = useState("single"); // "single" | "bulk"

  const [form, setForm] = useState(EMPTY_FORM);
  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [phoneLocalDigits, setPhoneLocalDigits] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey());
  const [status, setStatus] = useState("idle"); // idle | submitting | success | error
  const [errorMessage, setErrorMessage] = useState("");
  const [savedCustomer, setSavedCustomer] = useState(null);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleContactPersonChange(value) {
    if (!isInvalidContactPerson(value)) {
      updateField("contact_person", value);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");

    const validationError = validateBeforeSubmit(form, phoneLocalDigits);
    if (validationError) {
      setErrorMessage(validationError);
      setStatus("error");
      return;
    }

    setStatus("submitting");

    try {
      // Re-using the SAME idempotencyKey on a retry (e.g. the user clicking
      // Save again after a network error) is what makes this safe: the
      // backend treats the second call as a replay of the first, not a new
      // upsert with possibly-different in-flight state.
      const payload = buildSubmissionPayload(form, countryCode, phoneLocalDigits);
      const result = await submitBusinessMetadata(payload, idempotencyKey);
      setSavedCustomer(result);
      setStatus("success");
    } catch (err) {
      setErrorMessage(err.message || "Something went wrong. You can safely retry.");
      setStatus("error");
    }
  }

  function handleStartNew() {
    setForm(EMPTY_FORM);
    setCountryCode(DEFAULT_COUNTRY_CODE);
    setPhoneLocalDigits("");
    setSavedCustomer(null);
    setStatus("idle");
    // Only mint a NEW idempotency key when the user is starting a genuinely
    // new submission — not on every retry of the same one.
    setIdempotencyKey(newIdempotencyKey());
  }

  const disabled = status === "submitting";

  return (
    <div style={styles.page}>
      <div style={{ ...styles.card, ...(activeTab === "bookings" ? styles.cardWide : {}) }}>
        <div style={styles.tabContainer} role="tablist" aria-label="Main navigation">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "upload"}
            style={{ ...styles.tabBtn, ...(activeTab === "upload" ? styles.activeTabBtn : {}) }}
            onClick={() => setActiveTab("upload")}
          >
            Upload Metadata
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "bookings"}
            style={{ ...styles.tabBtn, ...(activeTab === "bookings" ? styles.activeTabBtn : {}) }}
            onClick={() => setActiveTab("bookings")}
          >
            Confirmed Bookings
          </button>
        </div>

        {activeTab === "upload" && (
          <div>
            <h1 style={styles.title}>Upload Business Metadata</h1>
            <p style={styles.subtitle}>
              This feeds the WhatsApp bot information to identify returning customers and personalize
              greetings. Submitting the same phone number again updates the existing record instead of
              creating a duplicate.
            </p>

            <div style={styles.modeToggle} role="tablist" aria-label="Upload mode">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "single"}
                style={{ ...styles.modeButton, ...(mode === "single" ? styles.modeButtonActive : {}) }}
                onClick={() => setMode("single")}
              >
                Single entry
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "bulk"}
                style={{ ...styles.modeButton, ...(mode === "bulk" ? styles.modeButtonActive : {}) }}
                onClick={() => setMode("bulk")}
              >
                Bulk upload (CSV)
              </button>
            </div>

            {mode === "bulk" ? (
              <CsvBulkUpload />
            ) : status === "success" ? (
              <div style={styles.successBox}>
                <p style={styles.successText}>
                  Saved <strong>{savedCustomer?.business_name}</strong> ({savedCustomer?.customer_id}).
                </p>
                <button style={styles.secondaryButton} onClick={handleStartNew}>
                  Add another business
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={styles.form}>
                <Field label="Business name" required>
                  <input
                    style={styles.input}
                    required
                    value={form.business_name}
                    onChange={(e) => updateField("business_name", e.target.value)}
                    disabled={disabled}
                  />
                </Field>

                <Field label="Phone number (WhatsApp)" required>
                  <PhoneField
                    countryCode={countryCode}
                    onCountryCodeChange={setCountryCode}
                    localDigits={phoneLocalDigits}
                    onLocalDigitsChange={setPhoneLocalDigits}
                    disabled={disabled}
                  />
                </Field>

                <Field label="Contact person">
                  <input
                    style={styles.input}
                    value={form.contact_person}
                    onChange={(e) => handleContactPersonChange(e.target.value)}
                    disabled={disabled}
                    placeholder="Full name"
                  />
                </Field>

                <Field label="Address">
                  <input
                    style={styles.input}
                    value={form.address}
                    onChange={(e) => updateField("address", e.target.value)}
                    disabled={disabled}
                  />
                </Field>

                <Field label="Sector">
                  <select
                    style={styles.input}
                    value={form.sector}
                    onChange={(e) => updateField("sector", e.target.value)}
                    disabled={disabled}
                  >
                    <option value="">Select a sector…</option>
                    {SECTORS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Business description">
                  <textarea
                    style={{ ...styles.input, height: 100, resize: "vertical" }}
                    placeholder="Founded year, owner, core products/services, team size, notable context…"
                    value={form.business_description}
                    onChange={(e) => updateField("business_description", e.target.value)}
                    disabled={disabled}
                  />
                </Field>

                {status === "error" && <p style={styles.errorText}>{errorMessage}</p>}

                <button type="submit" style={styles.primaryButton} disabled={disabled}>
                  {status === "submitting" ? "Saving…" : "Save business"}
                </button>
              </form>
            )}
          </div>
        )}

        {activeTab === "bookings" && <BookingsList />}
      </div>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <label style={styles.fieldLabel}>
      {label}
      {required ? " *" : ""}
      {children}
    </label>
  );
}

/** Bulk CSV upload: parses the file client-side and submits each row through
 * the exact same POST /customers endpoint as the single-entry form — no
 * backend changes. Each row gets its own Idempotency-Key, so re-uploading
 * the same file is safe (rows upsert on phone number, same as single entry). */
function CsvBulkUpload() {
  const [fileName, setFileName] = useState("");
  const [rows, setRows] = useState(null); // parsed rows awaiting upload
  const [parseError, setParseError] = useState("");
  const [results, setResults] = useState(null); // per-row outcome, after upload
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const fileInputRef = useRef(null);

  function resetForNewFile() {
    setRows(null);
    setResults(null);
    setParseError("");
    setProgress({ done: 0, total: 0 });
  }

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    resetForNewFile();
    if (!file) {
      setFileName("");
      return;
    }
    setFileName(file.name);

    try {
      const text = await file.text();
      const parsed = parseCsvToRows(text);
      if (parsed.length === 0) {
        setParseError("No data rows found in the file.");
        return;
      }
      setRows(parsed);
    } catch (err) {
      setParseError(err.message || "Could not parse this file.");
    }
  }

  async function handleUploadAll() {
    if (!rows || rows.length === 0) return;
    setProcessing(true);
    setProgress({ done: 0, total: rows.length });

    const outcomes = [];
    for (const { lineNumber, record } of rows) {
      const label = record.business_name || `(row ${lineNumber})`;
      const rowError = validateCsvRow(record);
      if (rowError) {
        outcomes.push({ lineNumber, label, status: "error", message: rowError });
        setProgress((p) => ({ ...p, done: p.done + 1 }));
        continue;
      }

      try {
        const payload = buildPayloadFromCsvRow(record);
        // Fresh idempotency key per ROW (each row is a distinct logical
        // submission) — but stable across a re-upload of the identical file,
        // since it's derived from the row content, so retrying the whole
        // file after a partial failure doesn't reprocess already-saved rows
        // with different in-flight state.
        const key = await stableRowIdempotencyKey(payload);
        const result = await submitBusinessMetadata(payload, key);
        outcomes.push({ lineNumber, label, status: "success", customerId: result.customer_id });
      } catch (err) {
        outcomes.push({ lineNumber, label, status: "error", message: err.message || "Upload failed." });
      }
      setProgress((p) => ({ ...p, done: p.done + 1 }));
    }

    setResults(outcomes);
    setProcessing(false);
  }

  function handleReset() {
    resetForNewFile();
    setFileName("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const successCount = results?.filter((r) => r.status === "success").length ?? 0;
  const errorCount = results?.filter((r) => r.status === "error").length ?? 0;

  return (
    <div style={styles.bulkContainer}>
      <p style={styles.bulkHelpText}>
        CSV columns: <code style={styles.code}>business_name</code>, <code style={styles.code}>phone_number</code>{" "}
        (required), plus optional <code style={styles.code}>contact_person</code>,{" "}
        <code style={styles.code}>address</code>, <code style={styles.code}>sector</code>,{" "}
        <code style={styles.code}>business_description</code>.{" "}
        <a href="/sample-customers.csv" download style={styles.link}>
          Download a sample CSV
        </a>
        .
      </p>

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,text/csv"
        onChange={handleFileChange}
        disabled={processing}
        style={styles.fileInput}
      />

      {parseError && <p style={styles.errorText}>{parseError}</p>}

      {rows && !results && (
        <div style={styles.bulkPreview}>
          <p style={styles.bulkPreviewText}>
            {fileName}: <strong>{rows.length}</strong> row{rows.length === 1 ? "" : "s"} ready to upload.
          </p>
          <button type="button" style={styles.primaryButton} onClick={handleUploadAll} disabled={processing}>
            {processing ? `Uploading ${progress.done}/${progress.total}…` : `Upload and save all ${rows.length}`}
          </button>
        </div>
      )}

      {results && (
        <div style={styles.bulkResults}>
          <p style={styles.bulkSummary}>
            <span style={styles.successText}>{successCount} saved</span>
            {errorCount > 0 && <span style={styles.errorText}> · {errorCount} failed</span>}
          </p>
          <div style={styles.resultsTableWrap}>
            <table style={styles.resultsTable}>
              <thead>
                <tr>
                  <th style={styles.resultsTh}>Row</th>
                  <th style={styles.resultsTh}>Business</th>
                  <th style={styles.resultsTh}>Result</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.lineNumber}>
                    <td style={styles.resultsTd}>{r.lineNumber}</td>
                    <td style={styles.resultsTd}>{r.label}</td>
                    <td style={styles.resultsTd}>
                      {r.status === "success" ? (
                        <span style={styles.successText}>✓ Saved ({r.customerId})</span>
                      ) : (
                        <span style={styles.errorText}>✗ {r.message}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" style={styles.secondaryButton} onClick={handleReset}>
            Upload another file
          </button>
        </div>
      )}
    </div>
  );
}

/** Derives a stable (non-random) idempotency key from a row's own content,
 * so re-uploading the exact same CSV — e.g. after fixing a typo in one row —
 * replays cleanly for rows that already succeeded instead of minting a new
 * key that would look like a brand-new submission. */
async function stableRowIdempotencyKey(payload) {
  const raw = `${payload.phone_number}|${payload.business_name}`;
  const bytes = new TextEncoder().encode(raw);
  const hashBuffer = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function PhoneField({ countryCode, onCountryCodeChange, localDigits, onLocalDigitsChange, disabled }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  const selected = COUNTRY_CODES.find((c) => c.code === countryCode) ?? COUNTRY_CODES[0];

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false);
      }
    }

    function handleEscape(e) {
      if (e.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div style={styles.phoneRow}>
      <div ref={rootRef} style={styles.countryRoot}>
        <button
          type="button"
          style={{ ...styles.countryTrigger, ...(disabled ? styles.disabled : {}) }}
          onClick={() => !disabled && setOpen((prev) => !prev)}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label="Country code"
        >
          <span>{selected.flag} {selected.dialCode}</span>
          <span style={{ ...styles.chevron, ...(open ? styles.chevronOpen : {}) }} aria-hidden>
            ▾
          </span>
        </button>

        {open && (
          <ul style={styles.countryMenu} role="listbox" aria-label="Country codes">
            {COUNTRY_CODES.map((country) => {
              const isSelected = country.code === countryCode;
              return (
                <li key={country.code} role="option" aria-selected={isSelected}>
                  <button
                    type="button"
                    style={{ ...styles.countryOption, ...(isSelected ? styles.countryOptionSelected : {}) }}
                    onClick={() => {
                      onCountryCodeChange(country.code);
                      setOpen(false);
                    }}
                  >
                    <span>{country.flag}</span>
                    <span>{country.dialCode}</span>
                    <span style={isSelected ? styles.countryNameSelected : styles.countryName}>
                      {country.name}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <input
        style={{ ...styles.input, ...styles.phoneInput }}
        type="tel"
        inputMode="numeric"
        pattern="[0-9]*"
        required
        placeholder="9876543210"
        value={localDigits}
        onChange={(e) => onLocalDigitsChange(sanitizePhoneDigits(e.target.value))}
        disabled={disabled}
        aria-label="Phone number"
      />
    </div>
  );
}

const fieldBase = {
  padding: "10px 12px",
  fontSize: 14,
  border: "1px solid #d0d3d9",
  borderRadius: 8,
  fontFamily: "inherit",
};

const toggleTrack = {
  display: "flex",
  marginBottom: 20,
  background: "#f0f1f4",
  borderRadius: 8,
  padding: 4,
};

const toggleBtn = {
  flex: 1,
  fontFamily: "inherit",
  border: "none",
  borderRadius: 6,
  background: "transparent",
  cursor: "pointer",
};

const toggleBtnActive = {
  background: "#fff",
  fontWeight: 600,
  color: "#2f6fed",
  boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
};

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-start",
    padding: "48px 16px",
    background: "#f5f6f8",
    fontFamily: "system-ui, -apple-system, sans-serif",
  },
  card: {
    width: "100%",
    maxWidth: 480,
    background: "#fff",
    borderRadius: 12,
    padding: 32,
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },
  cardWide: { maxWidth: 560 },
  tabContainer: { ...toggleTrack, gap: 8 },
  tabBtn: { ...toggleBtn, padding: "8px 16px", fontSize: 14, fontWeight: 500, color: "#57606a" },
  activeTabBtn: toggleBtnActive,
  title: { fontSize: 22, marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#555", marginBottom: 24, lineHeight: 1.5 },
  modeToggle: { ...toggleTrack, gap: 4 },
  modeButton: { ...toggleBtn, padding: "8px 12px", fontSize: 13, fontWeight: 600, color: "#555" },
  modeButtonActive: toggleBtnActive,
  form: { display: "flex", flexDirection: "column", gap: 16 },
  fieldLabel: { display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, color: "#333" },
  input: fieldBase,
  phoneRow: { display: "flex", gap: 8 },
  phoneInput: { flex: 1, minWidth: 0 },
  countryRoot: { position: "relative", flex: "0 0 auto", minWidth: 110 },
  countryTrigger: {
    ...fieldBase,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 6,
    width: "100%",
    padding: "10px 8px",
    background: "#fff",
    cursor: "pointer",
    color: "#111",
  },
  countryMenu: {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: 0,
    zIndex: 20,
    minWidth: 220,
    maxHeight: 200,
    margin: 0,
    padding: 4,
    listStyle: "none",
    background: "#fff",
    border: "1px solid #d0d3d9",
    borderRadius: 8,
    boxShadow: "0 4px 16px rgba(0, 0, 0, 0.12)",
    overflowY: "auto",
    overscrollBehavior: "contain",
    scrollbarWidth: "thin",
    scrollbarColor: "#c4c8d0 transparent",
  },
  countryOption: {
    display: "grid",
    gridTemplateColumns: "24px 52px 1fr",
    alignItems: "center",
    gap: 6,
    width: "100%",
    padding: "8px 10px",
    fontSize: 13,
    fontFamily: "inherit",
    textAlign: "left",
    border: "none",
    borderRadius: 6,
    background: "transparent",
    cursor: "pointer",
    color: "#222",
  },
  countryOptionSelected: {
    background: "#eef3fd",
    color: "#2f6fed",
    fontWeight: 600,
  },
  countryName: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#555" },
  countryNameSelected: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#2f6fed" },
  chevron: { fontSize: 12, color: "#666", transition: "transform 0.15s ease" },
  chevronOpen: { transform: "rotate(180deg)" },
  disabled: { opacity: 0.6, cursor: "not-allowed" },
  primaryButton: {
    marginTop: 8,
    padding: "12px 16px",
    fontSize: 15,
    fontWeight: 600,
    color: "#fff",
    background: "#2f6fed",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
  },
  secondaryButton: {
    padding: "10px 14px",
    fontSize: 14,
    background: "#fff",
    border: "1px solid #d0d3d9",
    borderRadius: 8,
    cursor: "pointer",
  },
  successBox: { display: "flex", flexDirection: "column", gap: 12 },
  successText: { fontSize: 14, color: "#1a7f37" },
  errorText: { fontSize: 13, color: "#c0342c" },
  bulkContainer: { display: "flex", flexDirection: "column", gap: 12 },
  bulkHelpText: { fontSize: 13, color: "#555", lineHeight: 1.6, margin: 0 },
  code: { background: "#f0f1f4", padding: "2px 5px", borderRadius: 4, fontSize: 12 },
  link: { color: "#2f6fed" },
  fileInput: { fontSize: 13, fontFamily: "inherit" },
  bulkPreview: { display: "flex", flexDirection: "column", gap: 10 },
  bulkPreviewText: { fontSize: 13, color: "#333", margin: 0 },
  bulkResults: { display: "flex", flexDirection: "column", gap: 10 },
  bulkSummary: { fontSize: 14, margin: 0 },
  resultsTableWrap: { maxHeight: 260, overflowY: "auto", border: "1px solid #e3e5e9", borderRadius: 8 },
  resultsTable: { width: "100%", borderCollapse: "collapse", fontSize: 12.5 },
  resultsTh: {
    textAlign: "left",
    padding: "8px 10px",
    background: "#f7f8fa",
    borderBottom: "1px solid #e3e5e9",
    position: "sticky",
    top: 0,
  },
  resultsTd: { padding: "8px 10px", borderBottom: "1px solid #f0f1f4" },
};
