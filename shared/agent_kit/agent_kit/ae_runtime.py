"""Agent Engine runtime helpers (Phase 8 increment 3).

The pieces an ADK agent needs when it runs on Agent Engine instead of the
local FastAPI adapter shells:

- a session-service factory for the ADK service registry
  (``cloudsql-iam://`` scheme) that builds ``DatabaseSessionService`` on a
  Cloud SQL AsyncConnector engine with IAM database authentication
  (D24 amendment 1: no passwords, the attached service account logs in);
- an httpx auth/client factory that mints audience-scoped ID tokens from
  the attached service account for MCP toolset connections to the
  IAM-allowlisted story/artifact servers;
- root-agent builders mirroring the local adapter assembly (prompt +
  immutable config, read-only tool filters).

Cloud imports are lazy so the module imports (and its URI/auth helpers unit
test) on machines without the connector package.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from google.adk.agents import LlmAgent
from google.adk.sessions import BaseSessionService

import httpx

from agent_kit.config import AgentConfig
from agent_kit.prompts import LoadedPrompt, load_prompt

CLOUDSQL_IAM_SCHEME = "cloudsql-iam"


def parse_cloudsql_iam_uri(uri: str) -> tuple[str, str]:
    """Split a ``cloudsql-iam:///<connection-name>/<database>`` registry
    URI into (connection name, database name).

    The connection name (``project:region:instance``) contains colons, so
    it travels in the path, never the netloc. Raises ValueError on a
    malformed URI (fail-loud at deployment startup).
    """
    parts = urlsplit(uri)
    if parts.scheme != CLOUDSQL_IAM_SCHEME:
        raise ValueError(f"unsupported session service scheme: {parts.scheme!r}")
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) != 2:
        raise ValueError(
            "expected cloudsql-iam:///<project>:<region>:<instance>/<database>"
        )
    return segments[0], segments[1]


def cloudsql_iam_session_service(uri: str, **kwargs):
    """Service-registry factory: a per-call DatabaseSessionService over an
    IAM-auth Cloud SQL engine for the given registry URI.

    The Agent Engine runtime serves each request in a fresh asyncio.run
    loop, so one persistent async engine/session-service cannot survive
    across requests (locks and pools bind to their first loop — observed
    as RuntimeError "is bound to a different event loop"). The returned
    service therefore builds one throwaway engine per call and disposes
    it afterwards; the facilitator's low turn frequency (≤10 turns per
    session, minutes apart) makes that overhead acceptable. The registry
    kwargs (e.g. agents_dir) are accepted and ignored.
    """
    connection_name, database = parse_cloudsql_iam_uri(uri)
    return _PerCallCloudSqlSessionService(connection_name, database)


class _PerCallCloudSqlSessionService(BaseSessionService):
    """Delegates every operation to a short-lived DatabaseSessionService
    on its own engine+connector (event-loop-safe by construction: one
    fresh engine AND one fresh Cloud SQL connector per operation, both
    disposed afterwards — the connector's aiohttp session must not
    outlive the request loop either)."""

    def __init__(self, connection_name: str, database: str):
        super().__init__()
        self._connection_name = connection_name
        self._database = database

    async def _call(self, name, *args, **kw):
        from google.adk.sessions import DatabaseSessionService
        from google.cloud.sql.connector import create_async_connector

        connector = await create_async_connector(enable_iam_auth=True)
        service = DatabaseSessionService(
            db_engine=_cloudsql_iam_engine(
                self._connection_name, self._database, connector
            )
        )
        try:
            return await getattr(service, name)(*args, **kw)
        finally:
            await service.db_engine.dispose()
            await connector.close_async()

    async def create_session(self, **kw):
        return await self._call("create_session", **kw)

    async def get_session(self, **kw):
        return await self._call("get_session", **kw)

    async def list_sessions(self, **kw):
        # NOTE: callers must not pass app_name in the payload — the AE
        # template injects its own (a duplicate raises TypeError at the
        # call boundary before any dedupe could run).
        return await self._call("list_sessions", **kw)

    async def delete_session(self, **kw):
        return await self._call("delete_session", **kw)

    async def append_event(self, *args, **kw):
        return await self._call("append_event", *args, **kw)


def resolve_cloudsql_iam_user(
    creds,
    env: dict | None = None,
    metadata_fetch=None,
) -> str:
    """Cloud SQL IAM login name of the effective principal.

    Attached compute credentials on Agent Engine report
    ``service_account_email == "default"``; the real email comes from the
    metadata server. An explicit ``CLOUDSQL_IAM_USER`` (env) wins — used
    for local repros. Service-account emails drop the
    ``.gserviceaccount.com`` suffix per the Cloud SQL convention.
    """
    import os

    env = env if env is not None else os.environ
    user = getattr(creds, "service_account_email", None)
    if not user or user == "default":
        user = env.get("CLOUDSQL_IAM_USER", "")
        if not user:
            if metadata_fetch is None:
                import urllib.request

                def metadata_fetch():  # noqa: F811
                    req = urllib.request.Request(
                        "http://metadata.google.internal/computeMetadata/v1/"
                        "instance/service-accounts/default/email",
                        headers={"Metadata-Flavor": "Google"},
                    )
                    return (
                        urllib.request.urlopen(req, timeout=10)
                        .read()
                        .decode()
                        .strip()
                    )

            user = metadata_fetch().strip()
    return user.removesuffix(".gserviceaccount.com")


def _cloudsql_iam_engine(connection_name: str, database: str, connector):
    """One throwaway SQLAlchemy async engine over the given (per-call)
    Cloud SQL async connector; IAM auth resolves the attached service
    account. No process-wide caching: the Agent Engine request loops are
    per-call, and engines/connectors must not outlive their loop. The
    caller disposes the engine and closes the connector afterwards.
    connector 1.22 exposes the async API as ``connect_async`` on the
    Connector (``create_async_connector`` only pins its loop)."""

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _connect():
        import asyncio

        import google.auth

        # connector 1.22: async drivers (asyncpg) must go through
        # ``connect_async`` — the sync ``connect`` runs a blocking
        # ``future.result()`` on the caller's loop and deadlocks it
        # (observed as create_session hanging forever on Agent Engine).
        # IAM auth additionally needs the explicit ``user`` (resolved
        # off the loop: the metadata-server fallback blocks).
        creds, _ = google.auth.default()
        user = await asyncio.to_thread(resolve_cloudsql_iam_user, creds)
        return await connector.connect_async(
            connection_name,
            "asyncpg",
            db=database,
            user=user,
        )

    # A plain `creator=` returning a raw coroutine bypasses SQLAlchemy's
    # asyncpg adaptation (the pool would hand the unawaited coroutine to
    # the dialect's connect events). The dialect's own dbapi wrapper is
    # the supported seam: it awaits the connector coroutine inside the
    # pool's greenlet context and returns the adapted connection.
    import asyncpg
    from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi

    adapted_dbapi = AsyncAdapt_asyncpg_dbapi(asyncpg)

    def creator():
        return adapted_dbapi.connect(async_creator_fn=_connect)

    # Driver URL is empty on purpose: the creator supplies every
    # connection (connector + IAM auth); URL.create keeps SQLAlchemy's
    # parser happy where a bare "postgresql+asyncpg://" string raises.
    # NullPool: no cross-request pool state on the per-request loop.
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        URL.create(drivername="postgresql+asyncpg"),
        creator=creator,
        poolclass=NullPool,
    )
    return engine


def register_cloudsql_iam_session_service() -> None:
    """Register the factory with the ADK service registry (deployed
    ``services.py`` entry point)."""
    from google.adk.cli.service_registry import get_service_registry

    get_service_registry().register_session_service(
        CLOUDSQL_IAM_SCHEME, cloudsql_iam_session_service
    )


class _IdTokenAuth(httpx.Auth):
    """httpx.Auth-style bearer injection of a refreshing audience-scoped
    ID token minted from the attached service account's metadata-server
    credentials. Only usable on GCP runtimes (Agent Engine, Cloud Run).
    Subclasses httpx.Auth on purpose: httpx validates `auth=` by
    isinstance and raises TypeError for duck-typed objects (observed
    live on Agent Engine)."""

    def __init__(self, audience: str):
        self._audience = audience
        self._credentials = None

    def _mint(self):
        import google.auth
        import google.auth.compute_engine
        import google.auth.transport.requests

        base, _ = google.auth.default()
        account = getattr(base, "service_account_email", None)
        if not account:
            raise RuntimeError(
                "audience ID tokens require an attached service account "
                "(metadata-server credentials); local runs use the compose "
                "stack instead"
            )
        return google.auth.compute_engine.IDTokenCredentials(
            request=google.auth.transport.requests.Request(),
            target_audience=self._audience,
            service_account_email=account,
        )

    def auth_flow(self, request):
        """httpx.Auth protocol: attach the bearer token, refreshing when
        expired (tokens live ~1 h; deployments outlive them)."""
        if self._credentials is None:
            self._credentials = self._mint()
        elif self._credentials.expired:
            import google.auth.transport.requests

            self._credentials.refresh(
                google.auth.transport.requests.Request()
            )
        request.headers["Authorization"] = f"Bearer {self._credentials.token}"
        yield request


def id_token_httpx_client_factory(audience: str):
    """``httpx_client_factory`` for ``StreamableHTTPConnectionParams``:
    a client whose every request carries a fresh audience-scoped ID token
    (the MCP ingress middleware validates exactly this audience)."""

    def _factory(headers=None, timeout=None, auth=None):
        import httpx

        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            auth=_IdTokenAuth(audience),
        )

    return _factory


def build_root_agent(
    slug: str,
    build_agent_fn,
    load_config_fn,
) -> LlmAgent:
    """Stateless AE root agent (reviewers, synthesis): prompt + immutable
    config, identical to the local adapter assembly minus the HTTP shell."""
    prompt: LoadedPrompt = load_prompt(slug)
    config: AgentConfig = load_config_fn()
    return build_agent_fn(prompt, config)


def build_facilitator_root_agent(
    slug: str,
    build_agent_fn,
    load_config_fn,
    *,
    story_url: str,
    artifact_url: str,
) -> LlmAgent:
    """Facilitator AE root agent: the local runner's read-only MCP
    toolsets (same tool filters as ``build_facilitator_runner``) with
    audience-scoped ID-token auth instead of the compose network.

    The adapter-side lineage tool guard is contextvar-bound to the local
    HTTP shell's request and has no Agent Engine equivalent yet; the
    AE-side enforcement point is decided with the increment-4 invocation
    contract (recorded in local-decisions). Tool filters plus the MCP
    ingress allowlists keep the facilitator at read-only access.
    """
    from google.adk.tools.mcp_tool.mcp_toolset import (
        McpToolset,
        StreamableHTTPConnectionParams,
    )

    from agent_kit.facilitator_adapter import (
        ARTIFACT_READ_TOOLS,
        STORY_TOOLS,
    )

    prompt: LoadedPrompt = load_prompt(slug)
    config: AgentConfig = load_config_fn()
    toolsets = [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=story_url,
                timeout=10.0,
                httpx_client_factory=id_token_httpx_client_factory(story_url),
            ),
            tool_filter=STORY_TOOLS,
        ),
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=artifact_url,
                timeout=10.0,
                httpx_client_factory=id_token_httpx_client_factory(
                    artifact_url
                ),
            ),
            tool_filter=ARTIFACT_READ_TOOLS,
        ),
    ]
    return build_agent_fn(prompt, config, tools=toolsets)


__all__ = [
    "build_facilitator_root_agent",
    "build_root_agent",
    "cloudsql_iam_session_service",
    "id_token_httpx_client_factory",
    "parse_cloudsql_iam_uri",
    "register_cloudsql_iam_session_service",
]
