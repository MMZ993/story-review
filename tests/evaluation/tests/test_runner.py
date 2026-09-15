"""Runner suite-level unit tests (filtering, isolation, summary, exits).

Drives ``run_deterministic_suite`` with injected fake transports over the
real t1 dataset files — no model calls, no stack.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from evaluation import runner as runner_module
from evaluation.runner import run_deterministic_suite

SESSION_ID = "sess-00000000-0000-0000-0000-000000000000"
RUN_ID = "run-00000000-0000-0000-0000-000000000000"


class GenericHttp:
    """Answers any case with a minimal completed-session arc."""

    def create_session(self, story_id, formats):
        return {"session_id": SESSION_ID, "story_run_id": RUN_ID, "state": "active"}

    def post_turn(self, session_id, body):
        return {"session_id": session_id, "turn_number": 2, "outcome": "finalize"}

    def get_session(self, session_id):
        return {"state": "completed", "facilitator_turn_count": 1, "turns": [],
                "artifact_references": [], "reports": []}

    def close(self):
        pass


class GenericArtifacts:
    def get_artifact(self, artifact_id, story_run_id):
        return {"content": {}}

    def close(self):
        pass


def make_factory(http=None, artifacts=None, fetch_agent_runs=None,
                 fetch_tool_calls=None, fail_on_case_id=None):
    def factory(args):
        from evaluation.case_runner import Transports

        http_impl = http or GenericHttp()

        class ExplodingHttp:
            def create_session(self, story_id, formats):
                if fail_on_case_id and story_id == fail_on_case_id:
                    raise RuntimeError("unexpected transport explosion")
                return http_impl.create_session(story_id, formats)

            def __getattr__(self, name):
                return getattr(http_impl, name)

        transports = Transports(
            http=ExplodingHttp(),
            artifacts=artifacts or GenericArtifacts(),
            fetch_agent_runs=fetch_agent_runs or (lambda dsn, sid: []),
            fetch_facilitator_tool_calls=fetch_tool_calls or (lambda dsn, sid: []),
            orchestration_dsn="dsn",
            facilitator_dsn="dsn",
        )
        return transports.http, transports.artifacts, transports

    return factory


def run_suite(tmp_path, monkeypatch, templates="t1", scenario=None, **factory_kwargs):
    args = type(
        "Args",
        (),
        {
            "templates": templates,
            "scenario": scenario,
            "base_url": "http://x",
            "artifact_url": "http://x",
            "orchestration_dsn": "dsn",
            "facilitator_dsn": "dsn",
        },
    )()
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(runner_module, "ARTIFACTS_DIR", artifacts_dir)
    exit_code = run_deterministic_suite(
        args, transport_factory=make_factory(**factory_kwargs)
    )
    return exit_code, artifacts_dir


def test_suite_runs_all_t1_cases_writes_artifacts_and_exits_nonzero(tmp_path, monkeypatch):
    exit_code, artifacts_dir = run_suite(tmp_path, monkeypatch)
    case_files = list((artifacts_dir / "cases").glob("*.json"))
    assert len(case_files) == 10  # t1 = 10 scenarios
    summary = json.loads((artifacts_dir / "summary.json").read_text())
    assert summary["total"] == 10
    assert exit_code == 1  # generic fakes do not satisfy the expectations


def test_suite_scenario_filter_runs_one_case(tmp_path, monkeypatch):
    exit_code, artifacts_dir = run_suite(tmp_path, monkeypatch, scenario="clean")
    summary = json.loads((artifacts_dir / "summary.json").read_text())
    assert summary["total"] == 1
    assert summary["results"][0]["case_id"].endswith("/clean")


def test_unexpected_exception_isolated_per_case(tmp_path, monkeypatch):
    # t1 clean story is story-01; explode only there
    exit_code, artifacts_dir = run_suite(
        tmp_path, monkeypatch, fail_on_case_id="story-01"
    )
    summary = json.loads((artifacts_dir / "summary.json").read_text())
    assert summary["total"] == 10  # every case still has a result
    exploded = [r for r in summary["results"] if r["status"] == "error"]
    assert len(exploded) == 1
    assert exit_code == 1


def test_unknown_template_fails_setup(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as excinfo:
        run_suite(tmp_path, monkeypatch, templates="t99")
    assert excinfo.value.code == 2
