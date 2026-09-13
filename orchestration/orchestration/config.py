"""Strict environment-driven configuration for the orchestration service.

Every operational constant comes from docs/design/observability.md
(timeouts, attempts, backoffs, request deadline, lease TTL); service
endpoints, database DSN, and artifact bucket come from the environment so
the same image runs locally (compose substitutes) and in Cloud Run.

Errors: ValueError from from_env() naming the first missing mandatory
variable — the service fails fast at startup rather than mid-request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .lease import TTL as _LEASE_TTL

_MANDATORY = (
    "ORCH_DB_DSN",
    "ORCH_STORY_URL",
    "ORCH_ARTIFACT_URL",
    "ORCH_REPORT_URL",
    "ORCH_BUCKET",
)

#: AE-mode pointer variables replacing the four adapter URLs (D25).
_AE_MANDATORY = _MANDATORY + (
    "ORCH_AE_BUSINESS_RESOURCE",
    "ORCH_AE_ENGINEERING_RESOURCE",
    "ORCH_AE_SYNTHESIS_RESOURCE",
    "ORCH_AE_FACILITATOR_RESOURCE",
    "ORCH_AE_BUSINESS_VERSION",
    "ORCH_AE_ENGINEERING_VERSION",
    "ORCH_AE_SYNTHESIS_VERSION",
    "ORCH_AE_FACILITATOR_VERSION",
)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration; constructed only via from_env()."""

    db_dsn: str
    story_url: str
    artifact_url: str
    report_url: str
    bucket: str
    # Local adapter invocation endpoints (frozen Phase 5 contract; the
    # local-agents compose profile publishes them on the host).
    business_url: str
    engineering_url: str
    synthesis_url: str
    facilitator_url: str
    # Observability.md: hard 5-minute end-to-end deadline for requests that
    # run agent work; short calls 60 s / 3 attempts; facilitator 120 s /
    # 2 attempts; session turn lease TTL 6 min (one minute past the deadline).
    request_deadline_seconds: int = 300
    short_call_timeout_seconds: int = 60
    short_call_attempts: int = 3
    facilitator_timeout_seconds: int = 120
    facilitator_attempts: int = 2
    lease_ttl_seconds: int = int(_LEASE_TTL.total_seconds())
    #: /health probe budget per downstream (observability.md specifies no
    #: value; 5 s keeps /health fast under full load).
    health_probe_timeout_seconds: int = 5
    #: Signed report download lifetime (observability.md prescribes no
    #: value; 15 min comfortably covers a review session handoff).
    signed_url_ttl_seconds: int = 900
    #: Local fake-gcs substitution endpoint (D15-5): when set, signed URLs
    #: are rewritten to this HTTPS URL and signed with the throwaway local
    #: key (signed_urls.py). None = real GCS / Phase 8.
    gcs_public_url: str | None = None
    #: MCP ingress auth (Phase 8 increment 4): when set, MCP calls carry
    #: audience-scoped ID-token bearer headers (deployed Cloud Run tier;
    #: connectivity-identity.md). Local/compose tiers keep it off.
    mcp_id_token_auth: bool = False
    #: Agent invocation mode (Phase 8 increment 4, D25): "http" = the
    #: local-adapter endpoints (compose/deterministic tier); "ae" = the
    #: deployed Agent Engine resources over the raw streamQuery REST
    #: surface (live tier, ae_client.py).
    agent_mode: str = "http"
    #: AE-mode pointers: full engine resource names plus deploy labels
    #: (the label is the audit agent_version in AE mode; D25 amendment).
    ae_business_resource: str | None = None
    ae_engineering_resource: str | None = None
    ae_synthesis_resource: str | None = None
    ae_facilitator_resource: str | None = None
    ae_business_version: str | None = None
    ae_engineering_version: str | None = None
    ae_synthesis_version: str | None = None
    ae_facilitator_version: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        """Build Settings from the environment (or an explicit mapping).

        Raises ValueError naming the first missing mandatory variable.
        """
        source = dict(os.environ) if env is None else env
        mode = source.get("ORCH_AGENT_MODE", "http").strip() or "http"
        if mode not in ("http", "ae"):
            raise ValueError(f"invalid ORCH_AGENT_MODE: {mode}")
        mandatory = _MANDATORY
        if mode == "ae":
            mandatory = _AE_MANDATORY
        values: dict[str, str] = {}
        for name in mandatory:
            values[name] = source.get(name, "").strip()
            if not values[name]:
                raise ValueError(f"missing mandatory environment variable: {name}")
        http_urls = {
            "ORCH_BUSINESS_URL": source.get("ORCH_BUSINESS_URL", "").strip(),
            "ORCH_ENGINEERING_URL": source.get("ORCH_ENGINEERING_URL", "").strip(),
            "ORCH_SYNTHESIS_URL": source.get("ORCH_SYNTHESIS_URL", "").strip(),
            "ORCH_FACILITATOR_URL": source.get("ORCH_FACILITATOR_URL", "").strip(),
        }
        if mode == "http":
            for name, value in http_urls.items():
                if not value:
                    raise ValueError(f"missing mandatory environment variable: {name}")
        values.update(http_urls)
        ae = {}
        for prefix in (
            "ORCH_AE_BUSINESS", "ORCH_AE_ENGINEERING",
            "ORCH_AE_SYNTHESIS", "ORCH_AE_FACILITATOR",
        ):
            for suffix in ("RESOURCE", "VERSION"):
                ae[f"{prefix}_{suffix}"] = source.get(f"{prefix}_{suffix}", "").strip()
        if mode == "ae":
            for name, value in ae.items():
                if not value:
                    raise ValueError(f"missing mandatory environment variable: {name}")
        return cls(
            mcp_id_token_auth=source.get("ORCH_MCP_ID_TOKEN_AUTH", "").strip()
            in {"1", "true", "True"},
            db_dsn=values["ORCH_DB_DSN"],
            story_url=values["ORCH_STORY_URL"],
            artifact_url=values["ORCH_ARTIFACT_URL"],
            report_url=values["ORCH_REPORT_URL"],
            bucket=values["ORCH_BUCKET"],
            business_url=values["ORCH_BUSINESS_URL"],
            engineering_url=values["ORCH_ENGINEERING_URL"],
            synthesis_url=values["ORCH_SYNTHESIS_URL"],
            facilitator_url=values["ORCH_FACILITATOR_URL"],
            gcs_public_url=source.get("ORCH_GCS_PUBLIC_URL", "").strip() or None,
            agent_mode=mode,
            ae_business_resource=ae["ORCH_AE_BUSINESS_RESOURCE"] or None,
            ae_engineering_resource=ae["ORCH_AE_ENGINEERING_RESOURCE"] or None,
            ae_synthesis_resource=ae["ORCH_AE_SYNTHESIS_RESOURCE"] or None,
            ae_facilitator_resource=ae["ORCH_AE_FACILITATOR_RESOURCE"] or None,
            ae_business_version=ae["ORCH_AE_BUSINESS_VERSION"] or None,
            ae_engineering_version=ae["ORCH_AE_ENGINEERING_VERSION"] or None,
            ae_synthesis_version=ae["ORCH_AE_SYNTHESIS_VERSION"] or None,
            ae_facilitator_version=ae["ORCH_AE_FACILITATOR_VERSION"] or None,
            signed_url_ttl_seconds=int(
                source.get("ORCH_SIGNED_URL_TTL_SECONDS", "900")
            ),
        )
