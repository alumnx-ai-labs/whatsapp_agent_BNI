"""Tests for calendar_data.py's Hello Oscar provider (issue #10 / PR #16 review).

No real Hello Oscar URL or Supabase project needed — both the Supabase client
and the httpx call are faked in-memory, matching the pattern the rest of this
repo uses for local testing (see CONTRIBUTING.md).
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


BOOKING_KWARGS = dict(
    title="Meeting with Sharma Traders",
    start_iso="2026-08-24T17:00:00+05:30",  # a Monday, 5pm IST
    duration_minutes=60,
    attendee_phone="+919999999999",
)


def test_hello_oscar_posts_to_chat_endpoint_with_expected_body(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("OSCAR_API_BASE_URL", "https://example-oscar.test")

    captured = {}

    def fake_post(self, url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"response": "Got it, scheduling now."}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = calendar_data.book_meeting(customer_id="CUST001", **BOOKING_KWARGS)

    assert captured["url"].endswith("/chat")
    assert captured["json"]["user_id"] == 5
    message = captured["json"]["message"]
    assert "Vijender" in message
    assert "Monday" in message
    assert "5 pm" in message and "6 pm" in message
    # attendee_name wasn't provided, so it falls back to the phone number
    assert "+919999999999" in message
    # location wasn't provided, so "at ..." should simply be absent
    assert " at " not in message
    # No auth header — the API is unauthenticated.
    assert not headers_have_auth(captured["headers"])
    assert result["rsvp_link"] == "Got it, scheduling now."


def headers_have_auth(headers) -> bool:
    if not headers:
        return False
    return any(k.lower() == "authorization" for k in headers)


def test_hello_oscar_handles_unexpected_response_shape_defensively(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("OSCAR_API_BASE_URL", "https://example-oscar.test")

    def fake_post(self, url, headers=None, json=None):
        request = httpx.Request("POST", url)
        # Response shape is unverified — simulate something with none of the
        # expected keys, to prove we don't crash on a KeyError.
        return httpx.Response(200, json={"some_other_field": "ok"}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = calendar_data.book_meeting(customer_id="CUST002", **BOOKING_KWARGS)
    assert result["rsvp_link"]  # falls back to a generic confirmation string


def test_hello_oscar_error_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("OSCAR_API_BASE_URL", "https://example-oscar.test")

    def fake_post(self, url, headers=None, json=None):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"error": "could not parse date"}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(calendar_data.HelloOscarError, match="could not parse date"):
        calendar_data.book_meeting(customer_id="CUST003", **BOOKING_KWARGS)


def test_hello_oscar_missing_base_url_raises_clear_error(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.delenv("OSCAR_API_BASE_URL", raising=False)

    with pytest.raises(calendar_data.HelloOscarError, match="OSCAR_API_BASE_URL"):
        calendar_data.book_meeting(customer_id="CUST004", **BOOKING_KWARGS)


def test_hello_oscar_includes_location_when_provided(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("OSCAR_API_BASE_URL", "https://example-oscar.test")

    captured = {}

    def fake_post(self, url, headers=None, json=None):
        captured["json"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"response": "Scheduled."}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    kwargs = dict(BOOKING_KWARGS)
    kwargs["attendee_name"] = "Anil"
    kwargs["location"] = "Taj Hotel"
    calendar_data.book_meeting(customer_id="CUST005b", **kwargs)

    message = captured["json"]["message"]
    assert "at Taj Hotel" in message
    assert "Anil" in message


def test_hello_oscar_booking_is_idempotent(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "hello_oscar")
    monkeypatch.setenv("OSCAR_API_BASE_URL", "https://example-oscar.test")

    calls = {"count": 0}

    def fake_post(self, url, headers=None, json=None):
        calls["count"] += 1
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"response": "Scheduled."}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    first = calendar_data.book_meeting(customer_id="CUST006", **BOOKING_KWARGS)
    second = calendar_data.book_meeting(customer_id="CUST006", **BOOKING_KWARGS)

    assert first["rsvp_link"] == second["rsvp_link"]
    assert calls["count"] == 1  # second call hit the idempotency short-circuit, not Hello Oscar again


def test_stub_provider_still_works_unchanged(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "stub")

    result = calendar_data.book_meeting(customer_id="CUST007", **BOOKING_KWARGS)
    assert result["rsvp_link"].startswith("https://calendar.app.google/")