#!/usr/bin/env bash
# Applies the ordered SQL migrations in deploy/cloud-sql/migrations/ to the
# database named by DATABASE_URL (postgres://user:pass@host:port/db).
#
# Each migration runs in its own transaction and is recorded in the
# schema_migrations table, so re-running the script is a no-op for already
# applied files. Uses psql when available; otherwise falls back to a
# throwaway postgres:16 container (host network) so the script also works on
# machines without a local psql client (repository-layout.md: the same script
# applies the schema to the compose Postgres substitute and, in Phase 8, to
# Cloud SQL via the Cloud SQL proxy).
#
# The DSN never appears in any process argv (Phase 8 deploy fix): it is
# parsed once into libpq's PG* environment variables, and psql (or the
# container fallback) receives only SQL as arguments — `ps` output on a
# shared host never leaks the credential. The first psql contact is retried
# a few times so a freshly started Postgres (pg_isready passing before the
# server accepts connections) does not fail the run.
#
# Usage:
#   DATABASE_URL=postgres://user:pass@127.0.0.1:9030/orchestration \
#     deploy/cloud-sql/run-migrations.sh
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
migrations_dir="$script_dir/migrations"

# Contact retries for a database that is still starting up (startup race:
# pg_isready can succeed before the server accepts real sessions).
CONTACT_RETRIES="${MIGRATION_CONTACT_RETRIES:-10}"
CONTACT_BACKOFF_SECONDS="${MIGRATION_CONTACT_BACKOFF_SECONDS:-1}"

dsn_to_pg_env() {
    # Parse a postgres:// DSN into KEY=VALUE lines for libpq's environment
    # (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE, percent-decoded). Only
    # the components present in the DSN are emitted. Query parameters
    # (e.g. ?sslmode=) are rejected — libpq does not take them from these
    # variables; configure TLS via the environment instead.
    python3 - "$1" <<'PY'
import sys
from urllib.parse import unquote, urlparse

url = sys.argv[1]
parsed = urlparse(url)
if parsed.scheme not in ("postgres", "postgresql"):
    sys.exit(f"unsupported DATABASE_URL scheme: {parsed.scheme!r}")
if parsed.query:
    sys.exit("DATABASE_URL query parameters are not supported")
host = parsed.hostname
port = parsed.port or 5432
path = parsed.path.lstrip("/")
if not path:
    sys.exit("DATABASE_URL must name a database")
out = []
if host:
    out.append(f"PGHOST={unquote(host)}")
out.append(f"PGPORT={port}")
if parsed.username:
    out.append(f"PGUSER={unquote(parsed.username)}")
if parsed.password is not None:
    out.append(f"PGPASSWORD={unquote(parsed.password)}")
out.append(f"PGDATABASE={unquote(path)}")
print("\n".join(out))
PY
}

require_database_url() {
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "ERROR: DATABASE_URL must be set (postgres://user:pass@host:port/db)" >&2
        exit 2
    fi
}

export_pg_env() {
    # Export the parsed DSN components for psql (and pass them through to
    # the docker fallback with explicit -e flags). A parse failure must
    # abort the script: `$(...)` inside a here-string does not trip
    # set -e on its own.
    local pg_env
    pg_env="$(dsn_to_pg_env "$DATABASE_URL")" || exit 2
    [ -n "$pg_env" ] || { echo "ERROR: DATABASE_URL parsed to nothing" >&2; exit 2; }
    local line key value
    while IFS='=' read -r key value; do
        [ -n "$key" ] || continue
        export "$key=$value"
    done <<<"$pg_env"
}

run_migrations() {
    if command -v psql >/dev/null 2>&1; then
        run_sql() { psql -v ON_ERROR_STOP=1 "$@"; }
    else
        # Assumption: Linux Docker — the container reaches the database over
        # the host network (127.0.0.1). Docker Desktop (macOS/Windows) host
        # networking is version-dependent; install a local psql there before
        # relying on this fallback. The PG* environment (never argv) carries
        # the connection parameters into the container.
        echo "psql not found; using throwaway postgres:16 container (host network)" >&2
        # The PG* environment (never argv) carries the connection
        # parameters into the container — including PGSSLMODE: Cloud SQL IAM
        # database authentication requires TLS, so it is forwarded even
        # though it never appears in the DSN.
        run_sql() {
            local env_args=()
            local var
            for var in PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE PGSSLMODE; do
                [ -n "${!var:-}" ] && env_args+=("-e" "$var")
            done
            docker run --rm -i --network host "${env_args[@]}" \
                postgres:16 psql -v ON_ERROR_STOP=1 "$@"
        }
    fi

    retry_first_contact() {
        # Tolerate a database that is still starting up (only the bootstrap
        # contact; SQL failures after it are real errors and fail fast).
        local attempt=1
        until "$@" >/dev/null 2>&1; do
            if [ "$attempt" -ge "$CONTACT_RETRIES" ]; then
                echo "ERROR: database not reachable after $CONTACT_RETRIES attempts" >&2
                return 1
            fi
            attempt=$((attempt + 1))
            sleep "$CONTACT_BACKOFF_SECONDS"
        done
    }

    # Bootstrap the tracking table, then apply every ordered file not yet recorded.
    retry_first_contact run_sql <<'SQL'
create table if not exists schema_migrations (
    name text primary key,
    applied_at timestamptz not null default now()
);
SQL

    applied=$(run_sql -t -A -c "select name from schema_migrations")

    for file in "$migrations_dir"/*.sql; do
        name="$(basename "$file")"
        if grep -qx "$name" <<<"$applied"; then
            echo "already applied: $name"
            continue
        fi
        echo "applying: $name"
        { echo "begin;";
          cat "$file";
          echo "insert into schema_migrations (name) values ('$name');";
          echo "commit;"; } | run_sql
    done

    echo "migrations up to date."
}

if [ "${BASH_SOURCE[0]}" == "$0" ]; then
    require_database_url
    export_pg_env
    run_migrations
fi
