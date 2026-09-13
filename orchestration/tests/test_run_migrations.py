"""run-migrations.sh deploy fixes (Phase 8 increment 0):

- the DATABASE_URL credential never appears in any process argv (parsed
  into libpq's PG* environment instead — verified through a psql wrapper
  that fails the run if it sees a DSN or misses the env vars);
- re-running the script is a no-op for already-applied migrations;
- DSN parsing handles percent-encoded credentials and rejects query
  parameters / foreign schemes.

Requires the throwaway Postgres of `make orchestration-test`
(ORCH_TEST_DB_DSN), same as the repository tests.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import asyncpg
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "cloud-sql" / "run-migrations.sh"

DSN = os.environ.get("ORCH_TEST_DB_DSN")


def _require_dsn() -> str:
    if not DSN:
        pytest.fail("ORCH_TEST_DB_DSN is not set — run tests via `make orchestration-test`")
    return DSN


def _parse_dsn(url: str) -> dict[str, str]:
    """Exercise the script's dsn_to_pg_env parser (source, then call)."""
    proc = subprocess.run(
        ["bash", "-c", f"source '{SCRIPT}' && dsn_to_pg_env \"$1\"", "_", url],
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(line.split("=", 1) for line in proc.stdout.splitlines() if line)


def test_dsn_to_pg_env_parses_components_with_decoding():
    env = _parse_dsn(
        "postgres://orch:p%40ss%3Aword@db.example.com:5433/orchestration"
    )
    assert env == {
        "PGHOST": "db.example.com",
        "PGPORT": "5433",
        "PGUSER": "orch",
        "PGPASSWORD": "p@ss:word",
        "PGDATABASE": "orchestration",
    }


def test_dsn_to_pg_env_defaults_port_and_omits_missing_components():
    env = _parse_dsn("postgresql://orch@localhost/mydb")
    assert env == {
        "PGHOST": "localhost",
        "PGPORT": "5432",
        "PGUSER": "orch",
        "PGDATABASE": "mydb",
    }


def test_dsn_to_pg_env_rejects_query_parameters():
    with pytest.raises(subprocess.CalledProcessError):
        _parse_dsn("postgres://u:p@h:5432/db?sslmode=require")


@pytest.mark.skipif(shutil.which("psql") is not None, reason="local psql present; docker fallback not exercised")
def test_docker_fallback_forwards_pgsslmode(tmp_path):
    """The throwaway-container fallback must forward PGSSLMODE alongside
    the other PG* variables: Cloud SQL IAM database authentication requires
    TLS, so the Phase-8 cloud run fails without it. A fake `docker` on PATH
    records its environment; no database is contacted."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    recorded = tmp_path / "docker-calls.txt"
    (fake_bin / "docker").write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$PGSSLMODE\" >> '{recorded}'\n"
        "exit 0\n"
    )
    (fake_bin / "docker").chmod(
        (fake_bin / "docker").stat().st_mode | stat.S_IEXEC
    )
    # python3 must stay reachable for dsn_to_pg_env; psql must NOT be.
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "DATABASE_URL": "postgres://u:p@127.0.0.1:5432/orchestration",
            "PGSSLMODE": "require",
        },
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "psql not found; using throwaway" in proc.stderr
    # bootstrap contact + applied-list select + one call per migration file:
    # the fake docker exits 0 without recording rows, so all five "apply"
    assert recorded.read_text().splitlines() == ["require"] * 7


@pytest.mark.skipif(shutil.which("psql") is None, reason="no local psql client")
async def test_migrations_apply_via_env_without_dsn_in_argv(tmp_path):
    """A psql wrapper that fails on any DSN-like argument and requires the
    parsed PG* environment proves the credential travels via env, not argv;
    a second run must be a no-op (every migration already recorded)."""
    dsn = _require_dsn()
    real_psql = shutil.which("psql")
    wrapper = tmp_path / "psql"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in postgres://*|postgresql://*) "
        "echo 'DSN in argv' >&2; exit 3;; esac\n"
        "done\n"
        "[ -n \"${PGDATABASE:-}\" ] && [ -n \"${PGHOST:-}\" ] "
        "|| { echo 'PG* env missing' >&2; exit 4; }\n"
        f"exec '{real_psql}' \"$@\"\n"
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)

    for run in (1, 2):
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            env={**os.environ, "DATABASE_URL": dsn, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "migrations up to date" in proc.stdout
        if run == 2:
            assert "applying:" not in proc.stdout  # everything already applied

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            names = await conn.fetch(
                "select name from schema_migrations order by name"
            )
    finally:
        await pool.close()
    recorded = {row["name"] for row in names}
    expected = {
        path.name for path in (SCRIPT.parent / "migrations").glob("*.sql")
    }
    assert recorded == expected
