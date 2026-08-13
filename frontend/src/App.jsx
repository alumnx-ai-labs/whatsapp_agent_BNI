import { useState } from "react";
import { newIdempotencyKey, submitBusinessMetadata } from "./api.js";

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
  phone_number: "",
  address: "",
  contact_person: "",
  sector: "",
  business_description: "",
};

export default function App() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey());
  const [status, setStatus] = useState("idle"); // idle | submitting | success | error
  const [errorMessage, setErrorMessage] = useState("");
  const [savedCustomer, setSavedCustomer] = useState(null);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus("submitting");
    setErrorMessage("");

    try {
      // Re-using the SAME idempotencyKey on a retry (e.g. the user clicking
      // Save again after a network error) is what makes this safe: the
      // backend treats the second call as a replay of the first, not a new
      // upsert with possibly-different in-flight state.
      const result = await submitBusinessMetadata(form, idempotencyKey);
      setSavedCustomer(result);
      setStatus("success");
    } catch (err) {
      setErrorMessage(err.message || "Something went wrong. You can safely retry.");
      setStatus("error");
    }
  }

  function handleStartNew() {
    setForm(EMPTY_FORM);
    setSavedCustomer(null);
    setStatus("idle");
    // Only mint a NEW idempotency key when the user is starting a genuinely
    // new submission — not on every retry of the same one.
    setIdempotencyKey(newIdempotencyKey());
  }

  const disabled = status === "submitting";

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Upload Business Metadata</h1>
        <p style={styles.subtitle}>
          This feeds the CRM the WhatsApp bot uses to identify returning customers and personalize
          greetings. Submitting the same phone number again updates the existing record instead of
          creating a duplicate.
        </p>

        {status === "success" ? (
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
              <input
                style={styles.input}
                required
                placeholder="+91 98765 43210"
                value={form.phone_number}
                onChange={(e) => updateField("phone_number", e.target.value)}
                disabled={disabled}
              />
            </Field>

            <Field label="Contact person">
              <input
                style={styles.input}
                value={form.contact_person}
                onChange={(e) => updateField("contact_person", e.target.value)}
                disabled={disabled}
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
  title: { fontSize: 22, marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#555", marginBottom: 24, lineHeight: 1.5 },
  form: { display: "flex", flexDirection: "column", gap: 16 },
  fieldLabel: { display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, color: "#333" },
  input: {
    padding: "10px 12px",
    fontSize: 14,
    border: "1px solid #d0d3d9",
    borderRadius: 8,
    fontFamily: "inherit",
  },
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
};
