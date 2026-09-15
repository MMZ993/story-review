"""Unit tests for the judge client retry/fail policy (Phase 9 increment 0).

Fixed policy per docs/quality/evaluation-tests.md: one stateless Vertex
call, temperature 0, one candidate; exactly one retry with identical input
on a transient transport failure; a second transport failure or an invalid
structured output fails the case; no best-of-N ever (no resampling, no
score selection). All tests run against a fake transport — no model calls.
"""

from __future__ import annotations

import json

import pytest

from evaluation.judge_client import (
    JudgeCallOutcome,
    JudgeFailure,
    JudgeTransportError,
    JudgeTransportReply,
    judge_case,
)
from evaluation.models import DIMENSIONS

CASE_ID = "clean-story-05"
PROMPT = "judge prompt text"


def judge_payload(passed: bool = True, delegation: int = 4) -> dict:
    return {
        "case_id": CASE_ID,
        "judge_model": "gemini-2.5-pro",
        "prompt_sha256": "b" * 64,
        "scores": [
            {"dimension": d, "score": delegation if d == "delegation" else 4,
             "rationale": "ok"}
            for d in DIMENSIONS
        ],
        "issues": [],
        "comment": "fine",
        "passed": passed,
    }


PUBLISHER = "gemini-2.5-pro-2025-XX"


def reply(payload: dict) -> JudgeTransportReply:
    return JudgeTransportReply(text=json.dumps(payload), publisher_model=PUBLISHER)


class Recorder:
    """Fake transport capturing every input for identical-retry checks."""

    def __init__(self, script):
        self.script = list(script)
        self.inputs: list[str] = []

    def __call__(self, contents: str) -> str:
        self.inputs.append(contents)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def run(recorder: Recorder) -> JudgeCallOutcome:
    return judge_case(
        case_id=CASE_ID,
        prompt_text=PROMPT,
        case_input={"transcript": "canned"},
        transport=recorder,
        judge_model="gemini-2.5-pro",
    )


def test_success_first_attempt():
    rec = Recorder([reply(judge_payload())])
    outcome = run(rec)
    assert outcome.result.passed is True
    assert outcome.attempts == 1
    assert len(rec.inputs) == 1


def test_one_transient_failure_retries_identically_then_succeeds():
    rec = Recorder([JudgeTransportError("connection reset"), reply(judge_payload())])
    outcome = run(rec)
    assert outcome.attempts == 2
    assert outcome.result.passed is True
    assert rec.inputs[0] == rec.inputs[1], "retry must reuse identical input"


def test_second_transport_failure_fails_case():
    rec = Recorder(
        [JudgeTransportError("503"), JudgeTransportError("503 again")]
    )
    with pytest.raises(JudgeFailure, match="transport failure"):
        run(rec)
    assert len(rec.inputs) == 2, "no third attempt allowed"


def test_invalid_structured_output_fails_without_retry():
    rec = Recorder([JudgeTransportReply(text="this is not json", publisher_model=PUBLISHER)])
    with pytest.raises(JudgeFailure, match="structured output"):
        run(rec)
    assert len(rec.inputs) == 1, "invalid output is not retryable"


def test_schema_invalid_payload_fails_without_retry():
    bad = judge_payload()
    bad["scores"] = bad["scores"][:3]
    rec = Recorder([JudgeTransportReply(text=json.dumps(bad), publisher_model=PUBLISHER)])
    with pytest.raises(JudgeFailure, match="structured output"):
        run(rec)
    assert len(rec.inputs) == 1


def test_publisher_metadata_recorded():
    rec = Recorder([reply(judge_payload())])
    outcome = run(rec)
    assert outcome.publisher_model == PUBLISHER
