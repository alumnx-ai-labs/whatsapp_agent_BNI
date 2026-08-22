import { useEffect, useState } from "react";
import { fetchConfirmedBookings } from "./api.js";

// Formats ISO timestamps into readable date & time (e.g., Aug 14, 2026 at 4:00 PM)
function formatDateTime(isoString) {
  if (!isoString) return "N/A";
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return isoString;

  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export default function BookingsList() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadBookings() {
    try {
      setLoading(true);
      setError("");
      const data = await fetchConfirmedBookings();
      setBookings(data);
    } catch (err) {
      setError(err.message || "Could not load bookings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBookings();
  }, []);

  if (loading) return <div style={{ textAlign: "center", padding: "40px", color: "#57606a" }}>Loading confirmed bookings...</div>;
  if (error) return <div style={{ color: "#c0342c", textAlign: "center", padding: "40px" }}>{error}</div>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 600, color: "#1f2328", margin: 0 }}>
          Confirmed Bookings ({bookings.length})
        </h2>
        <button type="button" style={styles.refreshBtn} onClick={loadBookings}>
          Refresh
        </button>
      </div>

      <div style={{ maxHeight: "500px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "12px", paddingRight: "4px" }}>
        {bookings.length === 0 ? (
          <p style={{ textAlign: "center", color: "#666", padding: "20px" }}>No confirmed bookings found.</p>
        ) : (
          bookings.map((item) => (
            <div key={item.id} style={styles.bookingCard}>
              <div style={styles.cardHeader}>
                <h3 style={styles.meetingTitle}>{item.title || "Confirmed Meeting"}</h3>
                <span style={styles.customerId}>ID: {item.customer_id}</span>
              </div>

              <div style={styles.cardBody}>
                <p style={styles.infoRow}>
                  <strong>Scheduled For:</strong> {formatDateTime(item.start_iso)}
                </p>
                <p style={{ ...styles.infoRow, color: "#6e7781", fontSize: "12px" }}>
                  <strong>Booked On:</strong> {formatDateTime(item.created_at)}
                </p>

                {item.rsvp_link && (
                  <div style={{ marginTop: "8px" }}>
                    <a
                      href={item.rsvp_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={styles.rsvpButton}
                    >
                      Open RSVP Calendar Link ↗
                    </a>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const styles = {
  refreshBtn: {
    padding: "6px 14px",
    borderRadius: "6px",
    border: "1px solid #d0d7de",
    background: "#ffffff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500",
    color: "#1f2328",
  },
  bookingCard: {
    border: "1px solid #e1e4e8",
    borderRadius: "10px",
    padding: "16px",
    background: "#ffffff",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  cardHeader: {
    marginBottom: "10px",
  },
  meetingTitle: {
    margin: 0,
    fontSize: "16px",
    fontWeight: "600",
    color: "#1f2328",
  },
  customerId: {
    fontSize: "12px",
    color: "#57606a",
    display: "block",
    marginTop: "2px",
    fontFamily: "monospace",
  },
  cardBody: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  infoRow: {
    margin: 0,
    fontSize: "14px",
    color: "#333333",
  },
  rsvpButton: {
    display: "inline-block",
    padding: "6px 12px",
    backgroundColor: "#0969da",
    color: "#ffffff",
    borderRadius: "6px",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: "500",
  },
};
