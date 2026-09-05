"""One-time admin session applying the connectivity-spike database bootstrap.

Purpose: apply 000_bootstrap.sql, 001_session_marker.sql, and 002_grants.sql
to the Cloud SQL instance as the built-in `postgres` admin user, using the
Cloud SQL Python Connector (no local proxy binary, ephemeral TLS certificate).
The admin password is supplied via the SPIKE_DB_PASSWORD environment variable
(set by the owner for this run only and rotated away afterwards per Runbook
06 increment 2.3); it is never logged or stored.

Inputs: PROJECT_ID, REGION, INSTANCE_NAME (default "<project>-sessions"),
SPIKE_DB_PASSWORD env vars. Side effects: creates the `spike` schema owned by
the sa-artifact-mcp IAM database user, the session_marker table, and
least-privilege grants. Errors: connector/auth failures raise; no partial-run
retries (statements are idempotent where practical).
"""

from __future__ import annotations

import os
import sys

from google.cloud.sql.connector import Connector

ROLE_TEMPLATE = "sa-artifact-mcp@{project}.iam"
SQL_FILES = ["000_bootstrap.sql", "001_session_marker.sql", "002_grants.sql"]
HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "europe-west4")
    instance = os.environ.get("INSTANCE_NAME", f"{project}-sessions")
    password = os.environ.get("SPIKE_DB_PASSWORD")
    missing = [
        name
        for name, value in {
            "PROJECT_ID": project,
            "SPIKE_DB_PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        print(f"missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    connection_name = f"{project}:{region}:{instance}"
    role = '"' + ROLE_TEMPLATE.format(project=project) + '"'  # quoted PG identifier

    with Connector() as connector:
        conn = connector.connect(
            connection_name,
            "psycopg",
            user="postgres",
            password=password,
            db="postgres",
            # 3307: Cloud SQL's dedicated port; some networks (like this one)
            # block outbound 5432 (gotcha recorded in Runbook 06).
            port=os.environ.get("SPIKE_DB_PORT", "3307"),
        )
        try:
            with conn.cursor() as cur:
                for filename in SQL_FILES:
                    path = os.path.join(HERE, filename)
                    with open(path, encoding="utf-8") as handle:
                        sql = handle.read().replace("__ROLE__", role)
                    print(f"applying {filename}")
                    cur.execute(sql)
            conn.commit()
        finally:
            conn.close()

    print("bootstrap complete: schema, table, and grants applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
