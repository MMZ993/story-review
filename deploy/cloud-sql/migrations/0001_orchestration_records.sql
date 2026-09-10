-- 0001: orchestration durable records (docs/design/schemas.md
-- "Durable Cloud SQL records" database constraints). These tables sit beside
-- the ADK DatabaseSessionService tables (facilitator adapter creates its own).

create table if not exists story_runs (
    story_run_id text primary key,
    story_id     text not null,
    state        text not null check (state in ('active', 'parked', 'finalizing', 'completed')),
    created_at   timestamptz not null,
    updated_at   timestamptz not null
);

-- At most one non-completed/non-parked run per story (api-contract: 409 on a
-- story that already has an active session; parked/completed runs free it).
create unique index if not exists one_active_run_per_story
    on story_runs (story_id)
    where state not in ('completed', 'parked');

-- Exactly one session per story run.
create table if not exists sessions (
    session_id              text primary key,
    story_run_id            text not null unique references story_runs (story_run_id),
    story_id                text not null,
    state                   text not null check (state in ('active', 'parked', 'finalizing', 'completed')),
    requested_formats       text[] not null,
    facilitator_turn_count  integer not null default 0 check (facilitator_turn_count between 0 and 10),
    final_review_reference  jsonb,
    report_references       jsonb not null default '[]'::jsonb,
    created_at              timestamptz not null,
    updated_at              timestamptz not null
);

-- One lease row per session; only its lease_token holder may renew/release
-- (enforced by the repository's conditional updates).
create table if not exists turn_leases (
    session_id  text primary key references sessions (session_id) on delete cascade,
    lease_token uuid not null,
    acquired_at timestamptz not null,
    expires_at  timestamptz not null
);

-- Exactly one authoritative TurnRecord per (session, turn number).
create table if not exists turns (
    session_id         text not null references sessions (session_id) on delete cascade,
    turn_number        integer not null check (turn_number >= 1),
    correlation_id     uuid not null,
    state              text not null check (state in ('pending', 'running', 'succeeded', 'failed')),
    po_message         text,
    po_accepted        boolean not null default false,
    facilitator_reply  text,
    delegation         jsonb,
    resolutions        jsonb not null default '[]'::jsonb,
    outcome            text check (outcome in ('continue', 'park', 'finalize')),
    produced_artifacts jsonb not null default '[]'::jsonb,
    created_at         timestamptz not null,
    completed_at       timestamptz,
    primary key (session_id, turn_number)
);

create table if not exists agent_runs (
    agent_run_id       text primary key,
    agent              text not null check (agent in
                         ('facilitator', 'business-reviewer', 'engineering-reviewer', 'synthesis')),
    agent_version      text not null,
    prompt_sha256      text not null,
    story_run_id       text not null references story_runs (story_run_id),
    session_id         text references sessions (session_id),
    correlation_id     uuid not null,
    input_references   jsonb not null default '[]'::jsonb,
    output_references  jsonb not null default '[]'::jsonb,
    state              text not null default 'pending'
                         check (state in ('pending', 'running', 'succeeded', 'failed')),
    transport_attempts integer not null default 0 check (transport_attempts between 0 and 3),
    corrective_reprompts integer not null default 0 check (corrective_reprompts between 0 and 2),
    started_at         timestamptz not null,
    finished_at        timestamptz
);

-- Idempotency keys are unique per route (+ session scope); '' marks the
-- session-less routes (POST /sessions). A claim is written in_progress with
-- the request fingerprint and completed with the stored canonical response.
create table if not exists idempotency_claims (
    route               text not null,
    session_id          text not null default '',
    idempotency_key     uuid not null,
    request_fingerprint text not null,
    state               text not null check (state in ('in_progress', 'completed')),
    canonical_response  jsonb,
    created_at          timestamptz not null,
    updated_at          timestamptz not null,
    primary key (route, session_id, idempotency_key)
);
