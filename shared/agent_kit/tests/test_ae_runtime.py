"""AE runtime helpers (Phase 8 increment 3) — deterministic tier.

Cloud imports (Cloud SQL connector, google.auth metadata credentials,
ADK MCP toolsets) stay behind the tested seams; here we test the pure
URI parsing, the fail-loud paths, and the token-refresh header injection
with fakes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_kit.ae_runtime import (
    _IdTokenAuth,
    parse_cloudsql_iam_uri,
)


class TestParseCloudsqlIamUri:
    def test_splits_connection_name_and_database(self):
        uri = "cloudsql-iam:///proj:region:instance/facilitator"
        assert parse_cloudsql_iam_uri(uri) == (
            "proj:region:instance",
            "facilitator",
        )

    def test_rejects_foreign_scheme(self):
        with pytest.raises(ValueError, match="scheme"):
            parse_cloudsql_iam_uri("postgres://user@host/db")

    def test_rejects_missing_database(self):
        with pytest.raises(ValueError, match="cloudsql-iam"):
            parse_cloudsql_iam_uri("cloudsql-iam:///proj:region:instance")

    def test_rejects_extra_segments(self):
        with pytest.raises(ValueError, match="cloudsql-iam"):
            parse_cloudsql_iam_uri("cloudsql-iam:///a/b/c")


class _FakeCredentials:
    def __init__(self, token: str, expired: bool = False):
        self.token = token
        self.expired = expired
        self.refreshed = 0

    def refresh(self, request):
        self.refreshed += 1
        self.token = f"rotated-{self.refreshed}"
        self.expired = False


class TestIdTokenAuth:
    def _flow(self, creds):
        auth = _IdTokenAuth.__new__(_IdTokenAuth)
        auth._audience = "https://story.example/mcp"
        auth._credentials = creds
        import httpx

        request = httpx.Request("POST", "https://story.example/mcp")
        next(auth.auth_flow(request))
        return request

    def test_attaches_bearer_token(self):
        request = self._flow(_FakeCredentials("tok-1"))
        assert request.headers["Authorization"] == "Bearer tok-1"

    def test_refreshes_expired_token(self):
        creds = _FakeCredentials("tok-1", expired=True)
        request = self._flow(creds)
        assert creds.refreshed == 1
        assert request.headers["Authorization"] == "Bearer rotated-1"

    def test_keeps_valid_token(self):
        creds = _FakeCredentials("tok-1")
        self._flow(creds)
        assert creds.refreshed == 0


class TestResolveCloudSqlIamUser:
    def test_service_account_email_stripped(self):
        from agent_kit.ae_runtime import resolve_cloudsql_iam_user

        creds = type("C", (), {"service_account_email": "sa-x@p.iam.gserviceaccount.com"})()
        assert resolve_cloudsql_iam_user(creds, env={}) == "sa-x@p.iam"

    def test_default_email_falls_back_to_env(self):
        from agent_kit.ae_runtime import resolve_cloudsql_iam_user

        creds = type("C", (), {"service_account_email": "default"})()
        got = resolve_cloudsql_iam_user(
            creds, env={"CLOUDSQL_IAM_USER": "repro@example.com"}, metadata_fetch=lambda: "x"
        )
        assert got == "repro@example.com"

    def test_default_email_falls_back_to_metadata(self):
        from agent_kit.ae_runtime import resolve_cloudsql_iam_user

        creds = type("C", (), {"service_account_email": "default"})()
        got = resolve_cloudsql_iam_user(
            creds,
            env={},
            metadata_fetch=lambda: "sa-y@p.iam.gserviceaccount.com\n",
        )
        assert got == "sa-y@p.iam"

    def test_user_account_without_email_raises_through_metadata(self):
        from agent_kit.ae_runtime import resolve_cloudsql_iam_user

        def boom():
            raise OSError("metadata unreachable")

        creds = type("C", (), {})()
        try:
            resolve_cloudsql_iam_user(creds, env={}, metadata_fetch=boom)
            raise AssertionError("expected OSError")
        except OSError:
            pass


class TestPerCallCloudSqlSessionService:
    @staticmethod
    def _stub_connector(monkeypatch, factory):
        import sys
        import types

        stub = types.ModuleType("google.cloud.sql.connector")
        stub.create_async_connector = factory
        for name in ("google.cloud", "google.cloud.sql", "google.cloud.sql.connector"):
            if name not in sys.modules and name != "google.cloud.sql.connector":
                monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        monkeypatch.setitem(sys.modules, "google.cloud.sql.connector", stub)

    def test_engine_and_connector_lifecycle_per_call(self, monkeypatch):
        import asyncio

        from agent_kit import ae_runtime

        made = []

        class FakeService:
            def __init__(self, db_engine):
                self.db_engine = db_engine
                self.disposed = False

            async def create_session(self, **kw):
                return {"ok": kw}

        class FakeEngine:
            def __init__(self):
                self.disposed = False

            async def dispose(self):
                self.disposed = True

        class FakeConnector:
            def __init__(self):
                self.closed = False

            async def close_async(self):
                self.closed = True

        def fake_engine(conn, db, connector):
            made.append(("engine", connector))
            return FakeEngine()

        def fake_dss(db_engine):
            made.append(("service", db_engine))
            return FakeService(db_engine)

        async def fake_connector(**kw):
            c = FakeConnector()
            made.append(("connector", kw.get("enable_iam_auth")))
            return c

        import sys

        import google.adk.sessions as sessions_mod

        self._stub_connector(monkeypatch, fake_connector)

        monkeypatch.setattr(ae_runtime, "_cloudsql_iam_engine", fake_engine)
        monkeypatch.setattr(sessions_mod, "DatabaseSessionService", fake_dss)

        svc = ae_runtime._PerCallCloudSqlSessionService("p:r:i", "db")
        out = asyncio.run(svc.create_session(user_id="u"))
        assert out == {"ok": {"user_id": "u"}}
        # one engine + connector per call, both released afterwards
        assert [m[0] for m in made] == ["connector", "engine", "service"]
        assert made[1][1].closed is True
        assert made[2][1].disposed is True

    def test_list_sessions_passthrough(self, monkeypatch):
        import asyncio

        from agent_kit import ae_runtime

        captured = {}

        class FakeService:
            def __init__(self, db_engine):
                self.db_engine = db_engine

            async def list_sessions(self, **kw):
                captured.update(kw)
                return []

        class FakeEngine:
            async def dispose(self):
                pass

        class FakeConnector:
            async def close_async(self):
                pass

        async def fake_connector(**kw):
            return FakeConnector()

        import google.adk.sessions as sessions_mod

        self._stub_connector(monkeypatch, fake_connector)

        monkeypatch.setattr(sessions_mod, "DatabaseSessionService", FakeService)
        monkeypatch.setattr(ae_runtime, "_cloudsql_iam_engine", lambda *a: FakeEngine())

        svc = ae_runtime._PerCallCloudSqlSessionService("p:r:i", "db")
        out = asyncio.run(svc.list_sessions(user_id="u"))
        assert out == []
        assert captured["user_id"] == "u"
        assert "app_name" not in captured


class TestIdTokenAuthHttpxContract:
    def test_is_an_httpx_auth_instance(self):
        """httpx validates `auth=` by isinstance (TypeError otherwise —
        observed live on Agent Engine at the inc-4 gate); the duck-typed
        auth_flow alone is not enough."""
        import httpx

        from agent_kit.ae_runtime import _IdTokenAuth

        assert isinstance(_IdTokenAuth("https://aud"), httpx.Auth)


class TestFacilitatorToolsetAudience:
    def test_audience_is_service_root_not_mcp_route(self):
        """Live-verified at the inc-4 gate: the ID-token audience must be
        the MCP service's root URL (the middleware's STORY_SERVICE_URL) —
        minting for the full /mcp route gets 401 from the ingress."""
        from agent_kit.ae_runtime import _audience_for

        assert _audience_for("https://svc.example.run.app/mcp") == (
            "https://svc.example.run.app"
        )
        assert _audience_for("https://svc.example.run.app") == (
            "https://svc.example.run.app"
        )


class TestIdTokenAuthInitialRefresh:
    def test_mint_refreshes_before_first_use(self, monkeypatch):
        """_mint must return credentials with a live token — the header is
        built from .token immediately (observed live as "Bearer None"
        → 401 at the inc-4 gate)."""
        import google.auth
        import google.auth.compute_engine

        from agent_kit.ae_runtime import _IdTokenAuth

        minted = {}

        class FakeBase:
            service_account_email = "default"

        class FakeIDTokenCredentials:
            def __init__(
                self,
                request,
                target_audience,
                service_account_email=None,
                use_metadata_identity_endpoint=False,
            ):
                minted["audience"] = target_audience
                minted["account"] = service_account_email
                minted["metadata_endpoint"] = use_metadata_identity_endpoint
                self.token = None

            def refresh(self, request):
                self.token = "tok"

        monkeypatch.setattr(google.auth, "default", lambda: (FakeBase(), None))
        monkeypatch.setattr(
            google.auth.compute_engine, "IDTokenCredentials", FakeIDTokenCredentials
        )
        auth = _IdTokenAuth("https://svc")
        creds = auth._mint()
        assert creds.token == "tok"
        assert minted["audience"] == "https://svc"

    def test_mint_uses_metadata_identity_endpoint_not_signblob(
        self, monkeypatch
    ):
        """The default IDTokenCredentials path builds an IAM Signer over
        the resolved account and mints the token via signBlob — AE's
        compute credentials report the account as ``default``, so IAM
        rejects it (400 "Invalid form of account ID default", observed
        live at the inc-6 gate: facilitator toolsets failed to load).
        With use_metadata_identity_endpoint=True the metadata identity
        endpoint mints the audience token directly, no signing."""
        import asyncio

        import google.auth
        import google.auth.compute_engine

        from agent_kit.ae_runtime import _IdTokenAuth

        minted = {}

        class FakeBase:
            service_account_email = "default"

        class FakeIDTokenCredentials:
            def __init__(
                self,
                request,
                target_audience,
                service_account_email=None,
                use_metadata_identity_endpoint=False,
            ):
                minted["account"] = service_account_email
                minted["metadata_endpoint"] = use_metadata_identity_endpoint
                self.token = None
                self.expired = False

            def refresh(self, request):
                self.token = "tok"

        monkeypatch.setattr(google.auth, "default", lambda: (FakeBase(), None))
        monkeypatch.setattr(
            google.auth.compute_engine, "IDTokenCredentials", FakeIDTokenCredentials
        )
        auth = _IdTokenAuth("https://svc")
        auth._mint()
        assert minted["metadata_endpoint"] is True
        assert minted["account"] is None


class TestFacilitatorRootAgentTelemetry:
    """Slice B (Item D): the AE facilitator root agent carries the same
    telemetry callbacks as the local runner — its model/tool calls must
    emit the content-safe storyreview.agent.* events."""

    def test_facilitator_root_agent_emits_model_and_tool_events(
        self, monkeypatch
    ):
        import logging

        from agent_kit.ae_runtime import build_facilitator_root_agent
        from agent_kit.config import AgentConfig

        captured: dict = {}

        def fake_build_agent(prompt, config, **kwargs):
            captured.update(kwargs)
            return object()  # root agent shell; callbacks are the subject

        class _Records(logging.Handler):
            records: list[logging.LogRecord] = []

            def emit(self, record):
                self.records.append(record)

        handler = _Records()
        for name in ("storyreview.agent.model", "storyreview.agent.tool"):
            logger = logging.getLogger(name)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        prompts_dir = Path(__file__).resolve().parents[3] / "prompts"
        monkeypatch.setenv("PROMPTS_DIR", str(prompts_dir))

        root = build_facilitator_root_agent(
            "facilitator",
            fake_build_agent,
            lambda: AgentConfig(
                model="gemini-test", location="europe-west4",
                temperature=0.0, max_output_tokens=1024,
            ),
            story_url="https://story.example.test/mcp",
            artifact_url="https://artifact.example.test/mcp",
        )
        assert root is not None
        assert captured["before_tool_callback"] is not None
        assert captured["after_tool_callback"] is not None
        assert captured["before_model_callback"] is not None
        assert captured["after_model_callback"] is not None

        class _Ctx:
            pass

        class _Request:
            model = "gemini-test"

        class _Response:
            partial = False
            model_version = "gemini-test"
            usage_metadata = None

        captured["before_model_callback"] = (
            captured["before_model_callback"]
            if isinstance(captured["before_model_callback"], list)
            else [captured["before_model_callback"]]
        )
        for before_model in captured["before_model_callback"]:
            before_model(_Ctx(), _Request())
        captured["after_model_callback"](_Ctx(), _Response())

        class _Tool:
            name = "noop"

        captured["before_tool_callback"](_Tool, {})
        captured["after_tool_callback"](_Tool, {}, _Ctx(), {})

        events = [(r.name, r.getMessage()) for r in _Records.records]
        assert ("storyreview.agent.model", "model_call") in events
        assert ("storyreview.agent.tool", "tool_call") in events
