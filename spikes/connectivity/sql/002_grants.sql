-- 002_grants.sql — least-privilege grants for the spike runtime role.
-- Applied by the one-time admin session (Runbook 06 increment 2.3);
-- __ROLE__ is substituted by sql/admin_apply.py with the IAM database
-- username (SA email without the ".gserviceaccount.com" suffix).

GRANT USAGE, CREATE ON SCHEMA spike TO __ROLE__;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA spike TO __ROLE__;
ALTER DEFAULT PRIVILEGES IN SCHEMA spike
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO __ROLE__;
