"""Tests for calendar_data.py's Hello Oscar provider (issue #10).

No real Supabase project or Hello Oscar API key needed — the Supabase client
and the httpx call are both faked in-memory, matching the pattern the rest of
this repo uses for local testing (see CONTRIBUTING.md).
"""
import httpx
import pytest

from app import calendar_data


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeMeetingsTable:
    """Enough of the Supabase query builder chain for book_meeting()."""

    def __init__(self, store):
        self._store = store
        self._filter_key = None
        self._insert_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, _column, value):
        self._filter_key = value
        return self

    def limit(self, _n):
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def execute(self):
        if self._insert_payload is not None:
            row = {"id": len(self._store) + 1, **self._insert_payload}
            self._store.append(row)
            return _FakeResponse([row])
        matches = [r for r in self._store if r["idempotency_key"] == self._filter_key]
        return _FakeResponse(matches)


class _FakeSupabaseClient:
    def __init__(self):
        self._meetings = []

    def table(self, name):
        assert name == "meetings"
        return _FakeMeetingsTable(self._meetings)


@pytest.fixture(autouse=True)
def fake_supabase(monkeypatch):
    client = _FakeSupabaseClient()
    monkeypatch.setattr(calendar_data, "get_client", lambda: client)
    return client


def test_hello_oscar_books_and_returns_rsvp_link(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("HELLO_OSCAR_API_KEY", "test-key")

    def fake_post(self, url, headers=None, json=None):
        assert url.endswith("/v1/events")
        assert headers["Authorization"] == "Bearer test-key"
        assert json["title"] == "Meeting with Acme"
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"id": "evt_hosc_123", "rsvp_url": "https://hellooscar.com/rsvp/evt_hosc_123"}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = calendar_data.book_meeting(
        title="Meeting with Acme",
        start_iso="2026-08-23T11:00:00+05:30",
        duration_minutes=30,
        attendee_phone="+919999999999",
        customer_id="CUST001",
    )

    assert result["rsvp_link"] == "https://hellooscar.com/rsvp/evt_hosc_123"
    assert result["duration_minutes"] == 30


def test_hello_oscar_booking_is_idempotent(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("HELLO_OSCAR_API_KEY", "test-key")

    calls = {"count": 0}

    def fake_post(self, url, headers=None, json=None):
        calls["count"] += 1
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"id": "evt_1", "rsvp_url": "https://hellooscar.com/rsvp/evt_1"}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    kwargs = dict(
        title="Meeting with Acme",
        start_iso="2026-08-23T11:00:00+05:30",
        duration_minutes=30,
        attendee_phone="+919999999999",
        customer_id="CUST001",
    )
    first = calendar_data.book_meeting(**kwargs)
    second = calendar_data.book_meeting(**kwargs)

    assert first["rsvp_link"] == second["rsvp_link"]
    assert calls["count"] == 1  # second call hit the idempotency short-circuit, not Hello Oscar again


def test_hello_oscar_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.delenv("HELLO_OSCAR_API_KEY", raising=False)

    with pytest.raises(calendar_data.HelloOscarError, match="HELLO_OSCAR_API_KEY"):
        calendar_data.book_meeting(
            title="Meeting with Acme",
            start_iso="2026-08-23T11:00:00+05:30",
            duration_minutes=30,
            attendee_phone="+919999999999",
            customer_id="CUST002",
        )


def test_stub_provider_still_works_unchanged(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "stub")

    result = calendar_data.book_meeting(
        title="Meeting with Acme",
        start_iso="2026-08-23T11:00:00+05:30",
        duration_minutes=30,
        attendee_phone="+919999999999",
        customer_id="CUST003",
    )
    assert result["rsvp_link"].startswith("https://calendar.app.google/")