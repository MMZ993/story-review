"""Judge stage wiring (Phase 9 increment 3).

Builds the judge case input for one executed case (captured typed outputs
+ the scenario's expected file as ground truth) and runs exactly one
judge call under the fixed policy (``judge_client.judge_case``): one
call, at most one identical retry, never best-of-N. The judge runs only
for cases that passed every deterministic assertion — cost control and
the designed gate order (deterministic first).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Protocol

from evaluation.capture import CaseCapture
from evaluation.judge_client import (
    JudgeCallOutcome,
    JudgeCaseFn,
    JudgeFailure,
    judge_case,
    live_transport,
)
from evaluation.judge_client import judge_case as default_judge_case


class ExpectedLike(Protocol):
    """The dataset's expected contract for one scenario (ExpectedCase)."""

    scenario: str

    def model_dump(self, **kwargs) -> dict: ...


def build_case_input(capture: CaseCapture, expected: ExpectedLike) -> dict:
    """Assemble the judge's single case input.

    Everything the judge may look at: the captured typed outputs (turns,
    artifacts, evidence, persistence probes) and the scenario's expected
    file (ground truth). ``prompt_sha256``/``judge_model`` identity fields
    are added by ``run_judge_for_case`` — the judge must echo them back.
    """
    return {
        "case_id": capture.case_id,
        "scenario": capture.scenario,
        "story_id": capture.story_id,
        "session_id": capture.session_id,
        "captured": capture.model_dump(mode="json"),
        "expected": expected.model_dump(mode="json"),
    }


def run_judge_for_case(
    *,
    capture: CaseCapture,
    expected: ExpectedLike,
    prompt_text: str,
    judge_model: str,
    prompt_sha256: str,
    transport: Any,
    judge_case: JudgeCaseFn = default_judge_case,
) -> dict:
    """Run one judge call and return the per-case artifact judge section.

    ``status`` is ``passed``/``failed`` per the typed verdict, or
    ``error`` when the judge call itself failed (invalid structured
    output or exhausted retry) — an error fails the case.
    """
    case_input = {
        **build_case_input(capture, expected),
        "case_id": capture.case_id,
        "prompt_sha256": prompt_sha256,
        "judge_model": judge_model,
    }
    try:
        outcome: JudgeCallOutcome = judge_case(
            case_id=capture.case_id,
            prompt_text=prompt_text,
            case_input=case_input,
            transport=transport,
            judge_model=judge_model,
        )
    except JudgeFailure as exc:
        return {"status": "error", "error": str(exc), "result": None}
    return {
        "status": "passed" if outcome.result.passed else "failed",
        "publisher_model": outcome.publisher_model,
        "attempts": outcome.attempts,
        "result": outcome.result.model_dump(mode="json"),
    }


def judge_smoke(config_path: Path, artifacts_dir: Path, eval_dir: Path) -> int:
    """One live judge call on the canned clean-case transcript (spend!).

    Writes the typed result + metadata to tests/evaluation/artifacts/.
    """
    cfg = load_judge_config(config_path)
    canned = json.loads(
        (eval_dir / "judge_smoke_case.json").read_text(encoding="utf-8")
    )
    transport = live_transport(cfg.model, cfg.location, cfg.temperature)
    try:
        outcome = judge_case(
            case_id=canned["case_id"],
            prompt_text=cfg.prompt_text,
            case_input={
            **canned["case_input"],
            "case_id": canned["case_id"],
            "prompt_sha256": cfg.judge_md_sha256,
            "judge_model": cfg.model,
        },
            transport=transport,
            judge_model=cfg.model,
        )
    except JudgeFailure as exc:
        print(f"judge smoke FAILED: {exc}", file=sys.stderr)
        return 1

    artifacts_dir.mkdir(exist_ok=True)
    artifact = {
        "case_id": canned["case_id"],
        "config": {
            "model": cfg.model,
            "location": cfg.location,
            "temperature": cfg.temperature,
            "candidate_count": cfg.candidate_count,
            "judge_md_sha256": cfg.judge_md_sha256,
        },
        "publisher_model": outcome.publisher_model,
        "attempts": outcome.attempts,
        "result": outcome.result.model_dump(mode="json"),
    }
    out_path = artifacts_dir / f"judge-smoke-{canned['case_id']}.json"
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(
        f"judge smoke PASS (passed={outcome.result.passed}, "
        f"publisher={outcome.publisher_model}, attempts={outcome.attempts}) "
        f"-> {out_path}"
    )
    return 0

