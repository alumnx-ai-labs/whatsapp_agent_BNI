// api.js — talks to the FastAPI backend's POST /customers endpoint.
// Idempotency: every submission carries a client-generated Idempotency-Key
// (a UUID). If the network drops after the server processed the request but
// before the response reached the browser, retrying with the SAME key
// returns the original cached response instead of creating/upserting again
// with different intermediate state. A fresh key is only generated for a
// genuinely new form session (see App.jsx).

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export function newIdempotencyKey() {
  return crypto.randomUUID();
}

export async function submitBusinessMetadata(payload, idempotencyKey, { retries = 2 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
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
        const detail = await res.text();
        throw new Error(`Server error (${res.status}): ${detail}`);
      }
      return await res.json();
    } catch (err) {
      lastError = err;
      // Safe to retry with the SAME idempotency key — the backend either
      // hasn't seen it yet, or already processed it and will just replay
      // the cached response.
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
        continue;
      }
    }
  }
  throw lastError;
}
