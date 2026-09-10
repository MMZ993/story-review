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
# Usage:
#   DATABASE_URL=postgres://user:pass@127.0.0.1:9030/orchestration \
#     deploy/cloud-sql/run-migrations.sh
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
migrations_dir="$script_dir/migrations"

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL must be set (postgres://user:pass@host:port/db)" >&2
    exit 2
fi

if command -v psql >/dev/null 2>&1; then
    run_sql() { psql -v ON_ERROR_STOP=1 "$DATABASE_URL" "$@"; }
else
    # Assumption: Linux Docker — the container reaches the database over the
    # host network (127.0.0.1). Docker Desktop (macOS/Windows) host networking
    # is version-dependent; install a local psql there before relying on this
    # fallback.
    echo "psql not found; using throwaway postgres:16 container (host network)" >&2
    run_sql() { docker run --rm -i --network host postgres:16 psql -v ON_ERROR_STOP=1 "$DATABASE_URL" "$@"; }
fi

# Bootstrap the tracking table, then apply every ordered file not yet recorded.
run_sql <<'SQL'
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
