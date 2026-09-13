"""One-time per-database admin bootstrap for the Cloud SQL PostgreSQL instance.

Purpose: PostgreSQL IAM database users are created with CONNECT only, and
PostgreSQL 16 revokes CREATE on schema public — so before an IAM-auth runtime
(or run-migrations.sh under an IAM role) can apply DDL, an admin session must
create the unit's database and grant the IAM role CREATE+USAGE on that
database's public schema. This replaces per-spike copies of the Runbook 06
`admin_apply.py` pattern for Phase 8 (docs/operations/connectivity-identity:
schema/grant bootstraps are one-time admin actions, by design runbook-driven).

Connects through the Cloud SQL Python Connector (no local proxy; ephemeral
certificate; port 3307 per the outbound-5432-block gotcha in Runbook 06) as
the built-in `postgres` admin using the SPIKE_DB_PASSWORD environment
variable (gitignored home.env, D7 stance: rare admin use, never logged).

Idempotent: re-running against an existing database only re-applies the
grants. CREATE DATABASE needs autocommit (outside any transaction).

Usage (repo root, after `source infra/envs/home.env`):
  DB_NAME=orchestration DB_ROLE_EMAIL=sa-orchestration@$PROJECT_ID.iam.gserviceaccount.com \
  uv run --no-project --with cloud-sql-python-connector --with 'psycopg[binary]' \
    python deploy/cloud-sql/admin-bootstrap.py

Inputs (env): PROJECT_ID, SPIKE_DB_PASSWORD, DB_NAME, DB_ROLE_EMAIL,
REGION (default europe-west4), INSTANCE_NAME (default <project>-sessions).
Errors: missing env vars or connector/SQL failures raise; CREATE DATABASE
duplicates are tolerated (idempotency). Exit codes: 0 ok, 2 bad input.
"""

from __future__ import annotations

import os
import sys

from google.cloud.sql.connector import Connector


def iam_db_username(role_email: str) -> str:
    """Cloud SQL convention: SA users drop the .gserviceaccount.com suffix."""
    return role_email.removesuffix(".gserviceaccount.com")


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    password = os.environ.get("SPIKE_DB_PASSWORD")
    db_name = os.environ.get("DB_NAME")
    role_email = os.environ.get("DB_ROLE_EMAIL")
    missing = [
        name
        for name, value in {
            "PROJECT_ID": project,
            "SPIKE_DB_PASSWORD": password,
            "DB_NAME": db_name,
            "DB_ROLE_EMAIL": role_email,
        }.items()
        if not value
    ]
    if missing:
        print(f"missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    region = os.environ.get("REGION", "europe-west4")
    instance = os.environ.get("INSTANCE_NAME", f"{project}-sessions")
    connection_name = f"{project}:{region}:{instance}"

    import re

    if not re.fullmatch(r"[a-z0-9_]+", db_name):
        print(f"invalid DB_NAME: {db_name!r}", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[\w.+@-]+", role_email):
        print(f"invalid DB_ROLE_EMAIL: {role_email!r}", file=sys.stderr)
        return 2

    role = '"' + iam_db_username(role_email) + '"'  # contains -/@ → quoted PG identifier

    with Connector() as connector:
        admin = connector.connect(
            connection_name,
            "psycopg",
            user="postgres",
            password=password,
            db="postgres",
            port=os.environ.get("SPIKE_DB_PORT", "3307"),
        )
        admin.autocommit = True  # CREATE DATABASE cannot run in a transaction
        try:
            exists = admin.execute(
                "select 1 from pg_database where datname = %s", (db_name,)
            ).fetchone()
            if exists:
                print(f"database already exists: {db_name}")
            else:
                admin.execute(f'create database "{db_name}"')
                print(f"created database: {db_name}")
        finally:
            admin.close()

        target = connector.connect(
            connection_name,
            "psycopg",
            user="postgres",
            password=password,
            db=db_name,
            port=os.environ.get("SPIKE_DB_PORT", "3307"),
        )
        try:
            with target.cursor() as cur:
                cur.execute(f"grant create, usage on schema public to {role}")
            target.commit()
            print(f"granted create,usage on {db_name}.public to {role}")
        finally:
            target.close()

    print("bootstrap complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
