-- 0005: anonymous per-user scoping (D24-3, docs/design/schemas.md
-- "Durable Cloud SQL records" / api-contract.md X-User-Id). Sessions and
-- story runs belong to the client-supplied user id; the
-- one-active-run-per-story rule becomes one active run per (user_id,
-- story_id). The constraint name is kept so the API's 409
-- STORY_SESSION_ACTIVE mapping (flows.map_constraint_violation) is
-- unchanged.

-- A single sentinel owner groups all pre-scoping rows (local compose
-- history): legacy sessions stay visible to that one legacy user id and
-- keep releasing their stories under the per-user index.
alter table story_runs add column user_id uuid;
update story_runs set user_id = '00000000-0000-4000-8000-000000000000';
alter table story_runs alter column user_id set not null;

alter table sessions add column user_id uuid;
update sessions s set user_id = r.user_id
    from story_runs r where s.story_run_id = r.story_run_id;
alter table sessions alter column user_id set not null;

-- Per-user one-active-run rule replaces the global one (same constraint
-- name; parked/completed runs still free the story — for their owner).
drop index if exists one_active_run_per_story;
create unique index one_active_run_per_story
    on story_runs (user_id, story_id)
    where state not in ('completed', 'parked');
