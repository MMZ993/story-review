"""Judge-wiring runner tests (Phase 9 increment 3).

_maybe_judge policy unit tests + suite-level trend append; no model
calls (fake judge transport).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation import runner as runner_module
from evaluation.judge_config import JudgeConfig
from evaluation.runner import _maybe_judge, run_deterministic_suite
from tests.test_runner import GenericArtifacts, GenericHttp, make_factory, run_suite


def make_cfg(tmp_path) -> JudgeConfig:
    return JudgeConfig(
        model="m",
        location="europe-west4",
        temperature=0.0,
        candidate_count=1,
        prompt_path=Path("prompts/judge.md"),
        prompt_text="PROMPT",
        judge_md_sha256="0" * 64,
    )


class Args:
    judge = False
    smoke = False
    config = "config.yaml"


class PassCapture:
    case_id = "t1/clean"
    scenario = "clean"
    story_id = "story-05"
    session_id = "s"
    story_run_id = "r"

    def model_dump(self, **_):
        return {"case_id": "t1/clean"}


class FakeCase:
    """Dataset Case stand-in: exposes .expected."""

    expected = None


class PassExpected:
    scenario = "clean"

    def model_dump(self, **_):
        return {}


class RecordingJudge:
    def __init__(self):
        self.calls = 0

    def __call__(self, contents):
        self.calls += 1
        raise AssertionError("transport should not be called in policy tests")


class StubTransport:
    """Returns a canned valid judge reply (one JSON object)."""

    def __call__(self, contents):
        from evaluation.judge_client import JudgeTransportReply

        payload = {
            "case_id": "t1/clean",
            "judge_model": "m",
            "prompt_sha256": "0" * 64,
            "scores": [
                {"dimension": d, "score": 4, "rationale": "ok"}
                for d in (
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
        return JudgeTransportReply(
            text=json.dumps(payload), publisher_model="m#1"
        )


def _case():
    from evaluation.capture import CaseCapture

    return CaseCapture(
        case_id="t1/clean",
        scenario="clean",
        template="t1",
        story_id="story-05",
        session_id="s",
        story_run_id="r",
    )


def test_maybe_judge_skips_failing_cases(tmp_path):
    judge = RecordingJudge()
    assert (
        _maybe_judge(Args(), make_cfg(tmp_path), judge, "failed", _case(), FakeCase())
        is None
    )
    assert judge.calls == 0


def test_maybe_judge_smoke_mode_judges_only_clean(tmp_path):
    args = Args()
    args.smoke = True
    assert (
        _maybe_judge(args, make_cfg(tmp_path), StubTransport(), "passed", _case(), FakeCase())
        is not None
    )
    # a non-clean scenario is never judged in smoke mode
    non_clean = _case().model_copy(update={"scenario": "conflicting"})
    assert (
        _maybe_judge(args, make_cfg(tmp_path), StubTransport(), "passed", non_clean, FakeCase())
        is None
    )


def test_suite_appends_trend_entry(tmp_path, monkeypatch):
    exit_code, artifacts_dir = run_suite(tmp_path, monkeypatch)
    trend = json.loads((artifacts_dir / "trend.json").read_text())
    assert len(trend) == 1
    assert trend[0]["total"] == 10
    assert (artifacts_dir / "trend.md").exists()


FakeCase.expected = PassExpected()
