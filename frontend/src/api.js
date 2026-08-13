// api.js — talks to the FastAPI backend's POST /customers endpoint.
// Idempotency: every submission carries a client-generated Idempotency-Key
// (a UUID). If the network drops after the server processed the request but
// before the response reached the browser, retrying with the SAME key
// returns the original cached response instead of creating/upserting again
// with different intermediate state. A fresh key is only generated for a
// genuinely new form session (see App.jsx).

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const BASE_DELAY_MS = 1000;
const DEFAULT_MAX_RETRIES = 3;

export function newIdempotencyKey() {
  return crypto.randomUUID();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Retry on network failures (no HTTP status) or 5xx server errors only. */
function isRetriableFailure(httpStatus) {
  return httpStatus == null || (httpStatus >= 500 && httpStatus <= 599);
}

export async function submitBusinessMetadata(payload, idempotencyKey, { retries = DEFAULT_MAX_RETRIES } = {}) {
  let lastError;

  for (let attempt = 0; attempt <= retries; attempt++) {
    let httpStatus;

    try {
      const res = await fetch(`${API_BASE}/customers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        httpStatus = res.status;
        const detail = await res.text();
        throw new Error(`Server error (${res.status}): ${detail}`);
      }

      return await res.json();
    } catch (err) {
      lastError = err;

      if (!isRetriableFailure(httpStatus) || attempt >= retries) {
        throw lastError;
      }

      // Exponential backoff: 1s, 2s, 4s, … — same Idempotency-Key on every attempt.
      await sleep(BASE_DELAY_MS * 2 ** attempt);
    }
  }

  throw lastError;
}
