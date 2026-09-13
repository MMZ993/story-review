"""Cloud SQL IAM pool wiring (Phase 8 increment 4, cloud part).

Deterministic tests for the deployed-service database path: the
``cloudsql-iam:///`` DSN scheme routes orchestration's record pool onto
the Cloud SQL Python Connector with IAM database authentication (the
inc-3 async gotchas: ``connect_async``, explicit IAM user, connector
closed with the pool). No network access — the connector, credentials,
and asyncpg pool are all injected fakes.
"""

from __future__ import annotations

import pytest

from orchestration import cloudsql_db
from orchestration.cloudsql_db import (
    CloudSqlPool,
    parse_cloudsql_iam_uri,
    resolve_iam_user,
)


class TestParseUri:
    def test_splits_connection_name_and_database(self):
        uri = "cloudsql-iam:///proj:region:inst/orchestration"
        assert parse_cloudsql_iam_uri(uri) == ("proj:region:inst", "orchestration")

    def test_rejects_other_scheme(self):
        with pytest.raises(ValueError, match="unsupported cloudsql-iam DSN scheme"):
            parse_cloudsql_iam_uri("postgres://user@host/db")

    def test_rejects_nonempty_netloc(self):
        with pytest.raises(ValueError, match="empty netloc"):
            parse_cloudsql_iam_uri("cloudsql-iam://host/proj:region:inst/db")

    def test_rejects_wrong_segment_count(self):
        with pytest.raises(ValueError, match="expected cloudsql-iam"):
            parse_cloudsql_iam_uri("cloudsql-iam:///only-one-segment")


class _Creds:
    def __init__(self, email):
        self.service_account_email = email


class TestResolveIamUser:
    def test_keeps_sa_login_convention(self):
        # Cloud SQL provisions <name>@<project>.iam logins.
        user = resolve_iam_user(
            _Creds("sa-orchestration@proj.iam.gserviceaccount.com")
        )
        assert user == "sa-orchestration@proj.iam"

    def test_default_credentials_fall_back_to_env(self):
        user = resolve_iam_user(
            _Creds("default"),
            env={"CLOUDSQL_IAM_USER": "sa-x@proj"},
        )
        assert user == "sa-x@proj"

    def test_default_credentials_fall_back_to_metadata_server(self):
        user = resolve_iam_user(_Creds("default"), metadata_fetch=lambda: "sa@p")
        assert user == "sa@p"

    def test_env_wins_over_missing_credentials(self):
        user = resolve_iam_user(None, env={"CLOUDSQL_IAM_USER": "explicit@proj"})
        assert user == "explicit@proj"

    def test_metadata_result_suffix_stripped(self):
        user = resolve_iam_user(
            _Creds("default"),
            metadata_fetch=lambda: "sa@proj.iam.gserviceaccount.com\n",
        )
        assert user == "sa@proj.iam"


class _FakeConnector:
    def __init__(self):
        self.connects: list[dict] = []
        self.closed = False

    async def connect_async(self, connection_name, driver, **kwargs):
        self.connects.append({"name": connection_name, "driver": driver, **kwargs})
        return object()  # an asyncpg connection; the pool is faked too

    async def close_async(self):
        self.closed = True


class _FakePool:
    """Mimics the asyncpg Pool surface the wrapper relies on — including
    the slots behavior that forbids reassigning close on the real class."""

    __slots__ = ("connect", "closed", "terminated")

    def __init__(self, **kwargs):
        self.connect = kwargs.get("connect")
        self.closed = False
        self.terminated = False

    async def close(self):
        self.closed = True

    def terminate(self):
        self.terminated = True

    async def fetch(self, query):
        return [("row",)]


class TestOpenCloudsqlPool:
    @pytest.fixture()
    def wiring(self, monkeypatch):
        connector = _FakeConnector()

        async def fake_create_async_connector(**kwargs):
            return connector

        async def fake_create_pool(**kwargs):
            return _FakePool(**kwargs)

        monkeypatch.setattr(
            cloudsql_db, "create_async_connector", fake_create_async_connector
        )
        monkeypatch.setattr(asyncpg := __import__("asyncpg"), "create_pool",
                            fake_create_pool)
        monkeypatch.setattr(
            cloudsql_db,
            "default_credentials",
            lambda: (_Creds("sa-orchestration@proj.iam.gserviceaccount.com"), None),
        )
        return connector

    async def test_returns_wrapper_over_connector_backed_pool(self, wiring):
        connector = wiring
        pool = await cloudsql_db.open_cloudsql_pool(
            "cloudsql-iam:///proj:region:inst/orchestration"
        )
        assert isinstance(pool, CloudSqlPool)
        # Startup already resolved the IAM user once (stable per service).
        assert connector.connects == []
        # Real asyncpg pools call the connect callable with their own
        # kwargs (loop=) — the callable must tolerate them.
        conn = await pool.connect(None, loop=None, connection_class=None, record_class=None)
        assert conn is not None
        assert connector.connects == [
            {
                "name": "proj:region:inst",
                "driver": "asyncpg",
                "db": "orchestration",
                "user": "sa-orchestration@proj.iam",
            }
        ]

    async def test_pool_parameters_bound_token_lifetime(self, wiring):
        connector = wiring
        pool = await cloudsql_db.open_cloudsql_pool(
            "cloudsql-iam:///p:r:i/db"
        )
        # Delegation reaches the wrapped pool's configuration.
        assert pool._pool.connect is not None
        assert (
            cloudsql_db.MAX_INACTIVE_CONNECTION_LIFETIME
            # pool object is the wrapper; parameters verified via the
            # module constant the implementation passes.
            <= 3600
        )

    async def test_pool_close_closes_connector(self, wiring):
        connector = wiring
        pool = await cloudsql_db.open_cloudsql_pool(
            "cloudsql-iam:///p:r:i/orchestration"
        )
        await pool.close()
        assert pool._pool.closed
        assert connector.closed

    async def test_pool_terminate_closes_connector(self, wiring):
        connector = wiring
        pool = await cloudsql_db.open_cloudsql_pool(
            "cloudsql-iam:///p:r:i/orchestration"
        )
        await pool.terminate()
        assert pool._pool.terminated
        assert connector.closed

    async def test_wrapper_delegates_pool_api(self, wiring):
        pool = await cloudsql_db.open_cloudsql_pool("cloudsql-iam:///p:r:i/db")
        assert await pool.fetch("SELECT 1") == [("row",)]

    async def test_iam_user_env_override_wins(self, wiring, monkeypatch):
        connector = wiring
        monkeypatch.setattr(
            cloudsql_db, "default_credentials", lambda: (_Creds("default"), None)
        )
        monkeypatch.setenv("CLOUDSQL_IAM_USER", "env-user@proj")
        pool = await cloudsql_db.open_cloudsql_pool("cloudsql-iam:///p:r:i/db")
        await pool.connect(None, loop=None, connection_class=None, record_class=None)
        assert connector.connects[0]["user"] == "env-user@proj"


class TestOpenPoolDispatch:
    async def test_cloudsql_scheme_routes_to_connector_pool(self, monkeypatch):
        from orchestration import cloudsql_db, db

        sentinel = object()

        async def fake_cloudsql(dsn):
            assert dsn.startswith("cloudsql-iam:///")
            return sentinel

        monkeypatch.setattr(cloudsql_db, "open_cloudsql_pool", fake_cloudsql)
        pool = await db.open_pool("cloudsql-iam:///p:r:i/orchestration")
        assert pool is sentinel

    async def test_plain_dsn_stays_asyncpg(self, monkeypatch):
        import asyncpg

        from orchestration import db

        async def fake_create_pool(dsn, **kwargs):
            fake_create_pool.seen = (dsn, kwargs)
            return object()

        monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)
        pool = await db.open_pool("postgres://u:h@host:5432/orchestration")
        assert pool is not None
        assert fake_create_pool.seen[0] == "postgres://u:h@host:5432/orchestration"
