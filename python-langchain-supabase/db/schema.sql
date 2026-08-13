-- Supabase / PostgreSQL schema for the WhatsApp Pain-Point Discovery Bot.
-- Run this in the Supabase SQL editor (or via `supabase db push`) before running the app.

create extension if not exists pgcrypto; -- for gen_random_uuid()

-- ── Customers (CRM) ─────────────────────────────────────────────
create table if not exists customers (
    customer_id        text primary key,
    business_name       text not null,
    phone_number         text not null,
    normalized_phone      text not null unique,   -- digits only, no country code — idempotency key for upserts
    address                text,
    contact_person          text,
    sector                   text,
    business_description      text,
    created_at                 timestamptz not null default now(),
    updated_at                  timestamptz not null default now()
);

-- ── Prior-interaction context (for personalized greetings) ─────
create table if not exists customer_context (
    customer_id            text primary key references customers(customer_id) on delete cascade,
    relationship_stage       text,
    last_interaction_date      date,
    total_interactions           int default 0,
    personal_notes                 jsonb default '{}'::jsonb,
    pain_points_raised              jsonb default '[]'::jsonb,
    conversation_history              jsonb default '[]'::jsonb,
    suggested_greeting_hint            text
);

-- ── Pain-point validation rubric ────────────────────────────────
create table if not exists pain_point_taxonomy (
    id                             serial primary key,
    category                        text not null,
    subtopic                         text not null,
    description                       text,
    example_phrases_keywords            text,
    valid_pain_point_example              text,
    invalid_non_pain_point_example          text
);

-- ── Conversation state (replaces in-memory session store) ──────
-- Persisting this to Postgres — instead of an in-memory dict — means the bot
-- survives restarts/redeploys mid-conversation and works correctly behind
-- multiple FastAPI worker processes (in-memory state would be per-process
-- and break as soon as you scale beyond one worker).
create table if not exists conversation_sessions (
    phone_number             text primary key,
    state                      text not null default 'START',
    elaboration_attempts         int not null default 0,
    customer_id                    text references customers(customer_id),
    customer_snapshot                jsonb,   -- cached full customer record (business_name, phone_number, etc.)
    pending_pain_point               text,
    validated_pain_point               jsonb,
    proposed_time                        text,
    updated_at                             timestamptz not null default now()
);

-- ── Inbound-message idempotency ─────────────────────────────────
-- WhatsApp providers (Twilio, Meta) retry webhook delivery on timeout/5xx.
-- Recording each provider message id here — and checking it BEFORE running
-- the flow — prevents the same inbound message from being processed twice
-- (which would otherwise double-advance the state machine or double-book a
-- meeting).
create table if not exists processed_messages (
    message_id        text primary key,
    phone_number         text,
    received_at             timestamptz not null default now()
);

-- ── Meetings (idempotent booking) ───────────────────────────────
create table if not exists meetings (
    id                     uuid primary key default gen_random_uuid(),
    customer_id              text references customers(customer_id),
    idempotency_key             text not null unique, -- e.g. f"{customer_id}:{start_iso}"
    start_iso                     text not null,
    title                            text not null,
    rsvp_link                          text,
    status                                text not null default 'confirmed',
    created_at                             timestamptz not null default now()
);

-- ── Generic API idempotency-key store (used by POST /customers) ─
create table if not exists api_idempotency_keys (
    idempotency_key      text primary key,
    response_body            jsonb not null,
    created_at                  timestamptz not null default now()
);

create index if not exists idx_customers_normalized_phone on customers(normalized_phone);
create index if not exists idx_processed_messages_phone on processed_messages(phone_number);
