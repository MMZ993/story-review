"""Agent adapter client transport policy tests (observability.md).

Reviewers/synthesis: 60 s / 3 attempts, jittered 1 s/2 s backoff.
Facilitator: 120 s / 2 attempts, 5 s backoff. Retry only on connection
failure, timeout, or a retryable adapter 5xx envelope; never on 4xx-class
envelopes. Attempts that cannot fit the remaining deadline are never
started. Purely seam-driven (no network, no real model).
"""

from __future__ import annotations

import pytest

from orchestration.agent_clients import (
    AgentCallFailure,
    AgentTransportError,
    FacilitatorInvocation,
    HttpReviewerClient,
    HttpSynthesisClient,
    HttpFacilitatorClient,
    ReviewerInvocation,
)

from .fakes import opening_turn_output, review_report, story_detail

CORR = "77777777-7777-4777-8777-777777777777"


def envelope(status: int, code: str, retryable: bool) -> tuple[int, dict]:
    return (
        status,
        {
            "error": {
                "code": code,
                "message": "boom",
                "agent": "business-reviewer",
                "correlation_id": CORR,
                "retryable": retryable,
                "retry_after_seconds": 5 if retryable else None,
            }
        },
    )


def reviewer_payload() -> dict:
    report = review_report("business", "story-07")
    return {
        "report": report.model_dump(mode="json"),
        "agent_version": "0.1.0",
        "prompt_sha256": "c" * 64,
    }


class PostRecorder:
    """Seam for HttpAgentClient: scripted (status, body) replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.sleeps: list[float] = []
        self.rng_values: list[float] = []

    async def post(self, url, json_body, timeout_s: float):
        self.calls.append(
            {"url": url, "json": json_body, "timeout_s": timeout_s}
        )
        if not self.replies:
            raise ConnectionError("down")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def rng(self) -> float:
        return 0.5


def make_client(kind: str, seam: PostRecorder):
    from .conftest import make_settings

    settings = make_settings()
    classes = {
        "reviewer": HttpReviewerClient,
        "synthesis": HttpSynthesisClient,
        "facilitator": HttpFacilitatorClient,
    }
    return classes[kind](
        f"http://{kind}:8080",
        settings,
        post=seam.post,
        sleeper=seam.sleep,
        rng=seam.rng,
    )


def invocation() -> ReviewerInvocation:
    return ReviewerInvocation(story=story_detail())


def facilitator_invocation(synthesis_reference) -> FacilitatorInvocation:
    return FacilitatorInvocation(
        session_id="sess-" + "a" * 32,
        turn_number=1,
        po_message=None,
        synthesis_report=None,  # patched per test via object.__new__? no — see below
        synthesis_reference=synthesis_reference,
    )


async def test_retryable_503_retried_until_success():
    seam = PostRecorder(
        [
            envelope(503, "UPSTREAM_UNAVAILABLE", True),
            envelope(503, "UPSTREAM_UNAVAILABLE", True),
            (200, reviewer_payload()),
        ]
    )
    client = make_client("reviewer", seam)
    result = await client.invoke(invocation())
    assert result.report.perspective == "business"
    assert result.transport_attempts == 3
    assert seam.calls[0]["url"].endswith("/invoke")
    assert len(seam.sleeps) == 2
    # half jitter with rng=0.5 -> exactly the base delays
    assert seam.sleeps == [1.0, 2.0]


async def test_non_retryable_422_not_retried():
    seam = PostRecorder([envelope(422, "VALIDATION_ERROR", False)])
    client = make_client("reviewer", seam)
    with pytest.raises(AgentCallFailure) as failure:
        await client.invoke(invocation())
    assert failure.value.error.code == "VALIDATION_ERROR"
    assert len(seam.calls) == 1


async def test_transport_exhaustion_raises_agent_transport_error():
    seam = PostRecorder([])
    client = make_client("reviewer", seam)
    with pytest.raises(AgentTransportError):
        await client.invoke(invocation())
    assert len(seam.calls) == 3


async def test_facilitator_two_attempts_and_fixed_backoff():
    facilitator_payload = {
        "output": opening_turn_output().model_dump(mode="json"),
        "agent_version": "0.1.0",
        "prompt_sha256": "e" * 64,
        "corrective_reprompts": 1,
    }
    seam = PostRecorder(
        [envelope(503, "UPSTREAM_UNAVAILABLE", True), (200, facilitator_payload)]
    )
    client = make_client("facilitator", seam)
    request = FacilitatorInvocation.model_construct(
        session_id="sess-" + "a" * 32,
        turn_number=1,
        po_message=None,
        synthesis_report=None,
        synthesis_reference=None,
    )
    result = await client.invoke(request)
    assert result.corrective_reprompts == 1
    assert len(seam.calls) == 2
    assert seam.calls[0]["url"].endswith("/turn")
    assert seam.sleeps == [5.0]
    assert seam.calls[0]["timeout_s"] == 120.0
