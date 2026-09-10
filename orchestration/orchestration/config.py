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
    "ORCH_BUSINESS_URL",
    "ORCH_ENGINEERING_URL",
    "ORCH_SYNTHESIS_URL",
    "ORCH_FACILITATOR_URL",
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

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        """Build Settings from the environment (or an explicit mapping).

        Raises ValueError naming the first missing mandatory variable.
        """
        source = dict(os.environ) if env is None else env
        values: dict[str, str] = {}
        for name in _MANDATORY:
            values[name] = source.get(name, "").strip()
            if not values[name]:
                raise ValueError(f"missing mandatory environment variable: {name}")
        return cls(
            db_dsn=values["ORCH_DB_DSN"],
            story_url=values["ORCH_STORY_URL"],
            artifact_url=values["ORCH_ARTIFACT_URL"],
            report_url=values["ORCH_REPORT_URL"],
            bucket=values["ORCH_BUCKET"],
            business_url=values["ORCH_BUSINESS_URL"],
            engineering_url=values["ORCH_ENGINEERING_URL"],
            synthesis_url=values["ORCH_SYNTHESIS_URL"],
            facilitator_url=values["ORCH_FACILITATOR_URL"],
        )
