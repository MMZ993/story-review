-- 000_bootstrap.sql — one-time admin bootstrap (run once as an admin session,
-- NOT part of the ordered application migrations; see Runbook 06 increment 2).
--
-- Purpose: PostgreSQL IAM database users are created with CONNECT privileges
-- only, and PostgreSQL 16 revokes CREATE on schema public. The spike schema
-- gives the sa-artifact-mcp IAM user its own DDL space. NOTE: Cloud SQL's
-- postgres admin cannot SET ROLE to IAM roles, so AUTHORIZATION is not
-- possible; the schema stays owned by postgres and 002_grants.sql grants the
-- IAM role USAGE+CREATE (it can create and fully control its tables there).
-- __ROLE__ is substituted by sql/admin_apply.py (IAM database username =
-- SA email without the ".gserviceaccount.com" suffix, emitted as a quoted
-- identifier).
-- The password used for the admin session is rotated away immediately after
-- (runbook procedure); the runtime service account never uses a password.

CREATE SCHEMA IF NOT EXISTS spike;
