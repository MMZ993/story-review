"""Evaluation suite runner (Phase 9 increment 0 — skeleton).

Loads and verifies the judge configuration, checks that the orchestration
base URL is reachable, and (optionally, owner-approved spend) performs the
one live judge smoke call on a canned clean-case transcript. Case
execution against the dataset arrives in increment 1
(case_runner/assertions); this skeleton exists so the make targets fail
cleanly and the judge path is proven before any suite spends Vertex
tokens.

Exit codes: 0 = requested work done; 2 = clean setup failure (stack
unreachable, config invalid) — not a test verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from evaluation.judge_client import JudgeFailure, judge_case, live_transport
from evaluation.judge_config import load_judge_config

EVAL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8130"
ARTIFACTS_DIR = EVAL_DIR / "artifacts"


def check_stack_reachable(base_url: str) -> None:
    """Fail cleanly (exit 2) when the orchestration stack is not up."""
    try:
        response = httpx.get(f"{base_url}/health", timeout=5.0)
    except httpx.HTTPError as exc:
        _fail_setup(f"orchestration unreachable at {base_url}: {exc}")
    if response.status_code >= 500:
        _fail_setup(
            f"orchestration /health returned {response.status_code} "
            "— bring the stack up first (make agents-compose-up)"
        )


def _fail_setup(message: str) -> None:
    print(f"evaluation: {message}", file=sys.stderr)
    raise SystemExit(2)


def judge_smoke(config_path: Path) -> int:
    """One live judge call on the canned clean-case transcript (spend!).

    Writes the typed result + metadata to tests/evaluation/artifacts/.
    """
    cfg = load_judge_config(config_path)
    canned = json.loads(
        (EVAL_DIR / "judge_smoke_case.json").read_text(encoding="utf-8")
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

    ARTIFACTS_DIR.mkdir(exist_ok=True)
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
    out_path = ARTIFACTS_DIR / f"judge-smoke-{canned['case_id']}.json"
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(
        f"judge smoke PASS (passed={outcome.result.passed}, "
        f"publisher={outcome.publisher_model}, attempts={outcome.attempts}) "
        f"-> {out_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluation")
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="orchestration base URL"
    )
    parser.add_argument(
        "--judge-smoke",
        action="store_true",
        help="run ONE live judge Vertex call on a canned transcript (spends tokens)",
    )
    parser.add_argument(
        "--config", default=str(EVAL_DIR / "config.yaml"), help="judge config path"
    )
    args = parser.parse_args(argv)

    # Config validity (incl. judge prompt SHA) is a precondition of everything.
    load_judge_config(args.config)

    if args.judge_smoke:
        return judge_smoke(Path(args.config))

    check_stack_reachable(args.base_url)
    print(
        "evaluation runner skeleton (Phase 9 increment 0): judge client ready, "
        "stack reachable; case execution arrives in increment 1 — nothing to run."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
