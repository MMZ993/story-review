-- 001_session_marker.sql — Phase 1 connectivity spike, ordered forward-only
-- migration. Creates ONLY the session-marker table (no other schema).
-- Rollback limitation: forward-only by design; the throwaway table is dropped
-- at spike teardown (documented in Runbook 06 increment 5).
--
-- Runs as the spike schema owner (sa-artifact-mcp's IAM database user), inside
-- schema `spike` (created by the one-time bootstrap, see 000_bootstrap.sql).
-- NOTE: the PostgreSQL role name for an IAM SA user drops the
-- ".gserviceaccount.com" suffix (Cloud SQL convention).

CREATE TABLE IF NOT EXISTS spike.session_marker (
    session_id     TEXT PRIMARY KEY,
    marker         TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
