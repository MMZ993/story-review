"""Judge-stage wiring unit tests (Phase 9 increment 3).

No model calls: the judge transport is a fake returning a canned valid
JudgeResult JSON. Covers the case-input shape, the judge-only-on-passed
policy, failure propagation, and smoke-mode judge eligibility.
"""

from __future__ import annotations

import json

from evaluation.judge_client import JudgeFailure, JudgeTransportReply
from evaluation.judge_stage import build_case_input, run_judge_for_case
from evaluation.models import JudgeResult
from evaluation.capture import CaseCapture


def make_capture() -> CaseCapture:
    return CaseCapture(
        case_id="t1/clean",
        scenario="clean",
        template="t1",
        story_id="story-05",
        session_id="sess-1",
        story_run_id="run-1",
        turns=[{"turn_number": 1, "outcome": "continue"}],
        final_detail={"state": "completed"},
    )


def valid_result_json(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "judge_model": "gemini-2.5-pro",
        "prompt_sha256": "0" * 64,
        "scores": [
            {"dimension": dim, "score": 4, "rationale": "fine"}
            for dim in (
                "review-coverage",
                "grounding",
                "conflict-resolution",
                "delegation",
                "final-state",
            )
        ],
        "issues": [],
        "comment": "ok",
        "passed": True,
    }


class FakeTransport:
    def __init__(self, payload: dict | None = None, raise_failure=None):
        self.payload = payload
        self.raise_failure = raise_failure
        self.calls: list[str] = []

    def __call__(self, contents: str) -> JudgeTransportReply:
        self.calls.append(contents)
        if self.raise_failure:
            raise self.raise_failure
        return JudgeTransportReply(
            text=json.dumps(self.payload), publisher_model="gemini-2.5-pro#1.0"
        )


class FakeExpected:
    scenario = "clean"

    def model_dump(self, **_):
        return {"scenario": "clean", "expected_final": {"state": "completed"}}


def test_build_case_input_carries_capture_and_expected_ground_truth():
    capture = make_capture()
    payload = build_case_input(capture, expected=FakeExpected())
    assert payload["case_id"] == "t1/clean"
    assert payload["captured"]["final_detail"] == {"state": "completed"}
    assert payload["expected"]["scenario"] == "clean"
    # ground-truth verdict fields are judge inputs, not judge outputs
    assert "passed" not in payload


def test_run_judge_for_case_returns_typed_outcome_and_echoes_identity():
    capture = make_capture()
    transport = FakeTransport(valid_result_json("t1/clean"))
    section = run_judge_for_case(
        capture=capture,
        expected=FakeExpected(),
        prompt_text="PROMPT",
        judge_model="gemini-2.5-pro",
        prompt_sha256="0" * 64,
        transport=transport,
    )
    assert section["status"] == "passed"
    assert section["publisher_model"] == "gemini-2.5-pro#1.0"
    assert section["attempts"] == 1
    assert section["result"]["passed"] is True
    # identity fields are injected server-side, not trusted from the payload
    sent = json.loads(transport.calls[0].split("CASE INPUT (JSON):\n", 1)[1])
    assert sent["prompt_sha256"] == "0" * 64
    assert sent["judge_model"] == "gemini-2.5-pro"


def test_run_judge_for_case_failed_verdict_is_status_failed():
    payload = valid_result_json("t1/clean")
    payload["scores"][0]["score"] = 2  # sub-threshold dimension
    payload["passed"] = False
    section = run_judge_for_case(
        capture=make_capture(),
        expected=FakeExpected(),
        prompt_text="PROMPT",
        judge_model="m",
        prompt_sha256="0" * 64,
        transport=FakeTransport(payload),
    )
    assert section["status"] == "failed"
    assert section["result"]["passed"] is False


def test_run_judge_for_case_judge_failure_is_status_error():
    section = run_judge_for_case(
        capture=make_capture(),
        expected=FakeExpected(),
        prompt_text="PROMPT",
        judge_model="m",
        prompt_sha256="0" * 64,
        transport=FakeTransport(raise_failure=JudgeFailure("invalid output")),
    )
    assert section["status"] == "error"
    assert "invalid output" in section["error"]
