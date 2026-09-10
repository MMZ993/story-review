"""Agent adapter invocation clients (frozen Phase 5 contract, mirrored).

Orchestration cannot import `agent_kit` (it would drag the ADK), so the
frozen local-adapter request/response shapes are mirrored here as strict
models; the shared `review_schemas` payload models are the authority for
everything nested. Fakes in the deterministic test tier implement the same
Protocols in-process (D15-3).

Transport policy per observability.md: reviewers and synthesis are short
calls (60 s / 3 attempts, half-jittered 1 s / 2 s backoff); the facilitator
uses 120 s / 2 attempts with a fixed 5 s backoff. Retry only on connection
failure, timeout, or a retryable adapter error envelope (5xx-class); never
on 4xx-class envelopes. Per-attempt timeouts clamp to the remaining
request deadline minus a cleanup reserve, and an attempt that cannot fit
is never started.
"""

from __future__ import annotations

import json
import random
import time
import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field
from review_schemas.errors import ErrorBody
from review_schemas.facilitator import FacilitatorTurnOutput
from review_schemas.review import ReviewReport, StoryDetail
from review_schemas.synthesis import ArtifactReference, SynthesisReport
from review_schemas.base import SessionId, Text

from .config import Settings

#: Budget kept aside for response persistence after the last attempt
#: (same reserve rule as the MCP wrapper).
RESPONSE_CLEANUP_RESERVE_SECONDS: float = 5.0

#: Facilitator backoff before the second attempt (observability.md).
FACILITATOR_BACKOFF_SECONDS: float = 5.0


class AgentCallFailure(Exception):
    """The adapter returned a terminal structured error envelope."""

    def __init__(self, error: ErrorBody):
        super().__init__(error.code)
        self.error = error


class AgentTransportError(Exception):
    """All transport attempts failed (connection/timeout)."""


class DeadlineExceeded(Exception):
    """Remaining request budget cannot fit another attempt."""


# --- frozen-contract mirrors ----------------------------------------------


class ReviewerInvocation(BaseModel):
    """`POST /invoke` body for a reviewer adapter (frozen contract)."""

    model_config = ConfigDict(extra="forbid")

    story: StoryDetail
    previous_review: ReviewReport | None = None
    extra_context: str | None = None


class PerspectivePair(BaseModel):
    """One perspective's synthesis input (report + its reference)."""

    model_config = ConfigDict(extra="forbid")

    report: ReviewReport
    reference: ArtifactReference


class SynthesisInvocation(BaseModel):
    """`POST /invoke` body for the synthesis adapter (frozen contract)."""

    model_config = ConfigDict(extra="forbid")

    business: PerspectivePair
    engineering: PerspectivePair


class FacilitatorInvocation(BaseModel):
    """`POST /turn` body for the facilitator adapter (frozen contract)."""

    model_config = ConfigDict(extra="forbid")

    session_id: SessionId
    turn_number: int = Field(ge=1, le=10)
    po_message: Text | None = None
    synthesis_report: SynthesisReport
    synthesis_reference: ArtifactReference
    evidence_references: list[ArtifactReference] = Field(default_factory=list)


@dataclass(frozen=True)
class ReviewerResult:
    """Reviewer adapter success + audit metadata (frozen contract)."""

    report: ReviewReport
    agent_version: str
    prompt_sha256: str
    transport_attempts: int = 1


@dataclass(frozen=True)
class SynthesisResult:
    """Synthesis adapter success + audit metadata (frozen contract)."""

    report: SynthesisReport
    agent_version: str
    prompt_sha256: str
    transport_attempts: int = 1


@dataclass(frozen=True)
class FacilitatorResult:
    """Facilitator adapter success + audit metadata (frozen contract,
    including the corrective-reprompt counter)."""

    output: FacilitatorTurnOutput
    agent_version: str
    prompt_sha256: str
    corrective_reprompts: int = 0
    transport_attempts: int = 1


class ReviewerClient(Protocol):
    async def invoke(
        self, request: ReviewerInvocation, *, deadline: float | None = None
    ) -> ReviewerResult: ...


class SynthesisClient(Protocol):
    async def invoke(
        self, request: SynthesisInvocation, *, deadline: float | None = None
    ) -> SynthesisResult: ...


class FacilitatorClient(Protocol):
    async def invoke(
        self, request: FacilitatorInvocation, *, deadline: float | None = None
    ) -> FacilitatorResult: ...


@dataclass(frozen=True)
class AgentSet:
    """The four downstream agent clients (injectable as one seam)."""

    business: ReviewerClient
    engineering: ReviewerClient
    synthesis: SynthesisClient
    facilitator: FacilitatorClient


# --- HTTP implementation ---------------------------------------------------

Post = Callable[[str, dict, float], Awaitable[tuple[int, dict]]]


async def _http_post(url: str, json_body: dict, timeout_s: float) -> tuple[int, dict]:
    """One real adapter round trip; returns (status, parsed JSON body)."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(url, json=json_body)
        return response.status_code, response.json()


class _HttpAgentClient:
    """Shared retry loop for one adapter endpoint.

    `kind` selects the policy: "short" (60 s / 3 / jittered 1 s, 2 s) or
    "facilitator" (120 s / 2 / fixed 5 s).
    """

    def __init__(
        self,
        url: str,
        settings: Settings,
        *,
        post: Post = _http_post,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: Callable[[], float] = random.random,
        kind: str = "short",
    ):
        self._url = url
        self._settings = settings
        self._post = post
        self._sleep = sleeper
        self._rng = rng
        self._kind = kind
        self._deadline: float | None = None

    @property
    def _attempts(self) -> int:
        if self._kind == "facilitator":
            return self._settings.facilitator_attempts
        return self._settings.short_call_attempts

    @property
    def _timeout(self) -> float:
        if self._kind == "facilitator":
            return float(self._settings.facilitator_timeout_seconds)
        return float(self._settings.short_call_timeout_seconds)

    async def _call(self, url: str, json_body: dict, deadline_at: float) -> tuple[int, dict]:
        """Run the retry loop against `url`; returns body + attempt count."""
        self._deadline = deadline_at
        last_transport_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            timeout_s = self._clamped_timeout(deadline_at)
            try:
                status, body = await self._post(url, json_body, timeout_s)
            except Exception as exc:  # connection / timeout
                last_transport_error = exc
                if attempt < self._attempts:
                    await self._backoff(attempt)
                    continue
                raise AgentTransportError(str(exc)) from exc
            if status == 200:
                return body, attempt
            error = self._error_body(status, body)
            if attempt < self._attempts and error.retryable:
                await self._backoff(attempt)
                continue
            raise AgentCallFailure(error)
        raise AgentTransportError(str(last_transport_error))

    def _error_body(self, status: int, body: dict) -> ErrorBody:
        """Parse the adapter's ErrorEnvelope; malformed bodies become a
        non-retryable UPSTREAM_UNAVAILABLE so they never loop."""
        try:
            fields = dict(body["error"])
            # strict mode needs a real UUID for correlation_id (JSON round trip)
            if isinstance(fields.get("correlation_id"), str):
                fields["correlation_id"] = uuid.UUID(fields["correlation_id"])
            error = ErrorBody.model_validate(fields)
        except Exception:
            # malformed body: a 5xx is still a retryable upstream failure
            retryable = status >= 500
            error = ErrorBody(
                code="UPSTREAM_UNAVAILABLE",
                message=f"adapter returned malformed error body (HTTP {status})",
                correlation_id=uuid.uuid4(),
                retryable=retryable,
                retry_after_seconds=5 if retryable else None,
            )
        return error

    def _clamped_timeout(self, deadline_at: float) -> float:
        """min(policy timeout, remaining budget - reserve); never started
        when the budget is exhausted."""
        remaining = deadline_at - time.monotonic() - RESPONSE_CLEANUP_RESERVE_SECONDS
        if remaining <= 0:
            raise DeadlineExceeded("request deadline budget exhausted")
        return min(self._timeout, remaining)

    async def _backoff(self, attempt: int) -> None:
        if self._kind == "facilitator":
            delay = FACILITATOR_BACKOFF_SECONDS
        else:
            base = (1.0, 2.0)[min(attempt - 1, 1)]
            delay = base * (0.5 + self._rng())
        # never sleep past the point where the next attempt cannot fit
        if self._deadline is None or time.monotonic() + delay < self._deadline:
            await self._sleep(delay)


class HttpReviewerClient(_HttpAgentClient):
    """`POST /invoke` reviewer adapter client."""

    PATH = "/invoke"

    async def invoke(
        self, request: ReviewerInvocation, *, deadline: float | None = None
    ) -> ReviewerResult:
        deadline_at = deadline or (
            time.monotonic() + self._settings.request_deadline_seconds
        )
        body, attempts = await self._call(
            self._url + self.PATH,
            {"story": request.story.model_dump(mode="json"),
             "previous_review": (
                 request.previous_review.model_dump(mode="json")
                 if request.previous_review
                 else None
             ),
             "extra_context": request.extra_context},
            deadline_at,
        )
        report = ReviewReport.model_validate_json(json.dumps(body["report"]))
        return ReviewerResult(
            report=report,
            agent_version=body["agent_version"],
            prompt_sha256=body["prompt_sha256"],
            transport_attempts=attempts,
        )


class HttpSynthesisClient(_HttpAgentClient):
    """`POST /invoke` synthesis adapter client."""

    PATH = "/invoke"

    async def invoke(
        self, request: SynthesisInvocation, *, deadline: float | None = None
    ) -> SynthesisResult:
        deadline_at = deadline or (
            time.monotonic() + self._settings.request_deadline_seconds
        )
        body, attempts = await self._call(
            self._url + self.PATH, request.model_dump(mode="json"), deadline_at
        )
        return SynthesisResult(
            report=SynthesisReport.model_validate_json(json.dumps(body["report"])),
            agent_version=body["agent_version"],
            prompt_sha256=body["prompt_sha256"],
            transport_attempts=attempts,
        )


class HttpFacilitatorClient(_HttpAgentClient):
    """`POST /turn` facilitator adapter client (session-scoped)."""

    PATH = "/turn"

    def __init__(self, url, settings, **kwargs):
        super().__init__(url, settings, kind="facilitator", **kwargs)

    async def invoke(
        self, request: FacilitatorInvocation, *, deadline: float | None = None
    ) -> FacilitatorResult:
        deadline_at = deadline or (
            time.monotonic() + self._settings.request_deadline_seconds
        )
        body, attempts = await self._call(
            self._url + self.PATH, request.model_dump(mode="json"), deadline_at
        )
        return FacilitatorResult(
            output=FacilitatorTurnOutput.model_validate_json(
                json.dumps(body["output"])
            ),
            agent_version=body["agent_version"],
            prompt_sha256=body["prompt_sha256"],
            corrective_reprompts=body.get("corrective_reprompts", 0),
            transport_attempts=attempts,
        )


def default_agent_set(settings: Settings) -> AgentSet:
    """Real HTTP clients for all four adapters (live tier, main PC only)."""
    return AgentSet(
        business=HttpReviewerClient(settings.business_url, settings),
        engineering=HttpReviewerClient(settings.engineering_url, settings),
        synthesis=HttpSynthesisClient(settings.synthesis_url, settings),
        facilitator=HttpFacilitatorClient(settings.facilitator_url, settings),
    )
