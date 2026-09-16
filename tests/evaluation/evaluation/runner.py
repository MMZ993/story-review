"""Evaluation suite runner (Phase 9).

Increment 0: judge config verification + stack reachability + optional
live judge smoke.

Increment 1: deterministic case execution (judge OFF). Loads the dataset
cases via the dataset loader, replays each ``po_script`` over the compose
orchestration API (``case_runner``), evaluates every deterministic
assertion (``assertions``), writes per-case JSON artifacts + a summary,
and exits 1 when any case fails. Judge wiring arrives in increment 3.

Exit codes: 0 = all requested cases passed; 1 = at least one case
failed; 2 = clean setup failure (stack unreachable, config invalid,
dataset unreadable) — not a test verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from dataset_loader.dataset import expand_cases, load_all_stories, load_expected
from evaluation.artifact_client import ArtifactClient, ArtifactClientError
from evaluation.assertions import evaluate_case
from evaluation.case_runner import CaseFailure, Transports, run_case
from evaluation.db_evidence import (
    fetch_agent_runs,
    fetch_facilitator_tool_calls,
)
from evaluation.judge_client import live_transport
from evaluation.judge_config import load_judge_config
from evaluation.judge_stage import judge_smoke, run_judge_for_case
from evaluation.trend import append_trend
from evaluation.orchestration_client import OrchestrationClient

EVAL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8130"
DEFAULT_ARTIFACT_URL = "http://127.0.0.1:8102"
DEFAULT_ORCHESTRATION_DSN = (
    "postgresql://facilitator:facilitator@127.0.0.1:15432/orchestration"
)
DEFAULT_FACILITATOR_DSN = (
    "postgresql://facilitator:facilitator@127.0.0.1:15432/facilitator"
)
ARTIFACTS_DIR = EVAL_DIR / "artifacts"


def check_stack_reachable(base_url: str) -> None:
    """Fail cleanly (exit 2) when the orchestration stack is not up."""
    try:
        response = httpx.get(f"{base_url}/health", timeout=5.0)
    except httpx.HTTPError as exc:
        _fail_setup(f"orchestration unreachable at {base_url}: {exc}")
    if response.status_code < 200 or response.status_code >= 500:
        _fail_setup(
            f"orchestration /health returned {response.status_code} "
            "— bring the stack up first (make agents-compose-up)"
        )
    try:
        status = response.json().get("status")
    except ValueError:
        status = None
    # degraded is acceptable (MCP cold starts scale-to-zero); the per-case
    # retry discipline handles it — but a foreign 2xx body is a wrong URL.
    if status not in {"ok", "degraded"}:
        _fail_setup(
            f"orchestration /health at {base_url} is not this API "
            f"(status body: {status!r})"
        )


def _fail_setup(message: str) -> None:
    print(f"evaluation: {message}", file=sys.stderr)
    raise SystemExit(2)



def run_deterministic_suite(args, transport_factory=None, judge_transport=None) -> int:
    """Execute the selected dataset cases; judge ON only when requested.

    Increment 3: with ``--judge``, every case that passes all
    deterministic assertions additionally gets exactly one judge call
    (cost control + designed gate order); ``--smoke`` restricts judging to
    the single ``clean`` happy path while still running the full selected
    template set deterministically — the pipeline-gate smoke set.

    ``transport_factory(args)`` builds the (http, artifacts, Transports)
    triple; ``judge_transport`` replaces the live judge transport; tests
    inject fakes for both, the default builds the real clients.
    """
    if transport_factory is not None:
        http, artifacts, transports = transport_factory(args)
    else:
        check_stack_reachable(args.base_url)
        http = OrchestrationClient(
            transport=httpx.HTTPTransport(),
            base_url=args.base_url,
        )
        artifacts = ArtifactClient(
            transport=httpx.HTTPTransport(), base_url=args.artifact_url
        )
        try:
            artifacts.initialize()
        except ArtifactClientError as exc:
            _fail_setup(f"artifact MCP unreachable at {args.artifact_url}: {exc}")
        transports = Transports(
            http=http,
            artifacts=artifacts,
            fetch_agent_runs=fetch_agent_runs,
            fetch_facilitator_tool_calls=fetch_facilitator_tool_calls,
            orchestration_dsn=args.orchestration_dsn,
            facilitator_dsn=args.facilitator_dsn,
        )
    judge_cfg = None
    if judge_transport is None and (getattr(args, "judge", False) or getattr(args, "smoke", False)):
        try:
            judge_cfg = load_judge_config(Path(args.config))
            judge_transport = live_transport(
                judge_cfg.model, judge_cfg.location, judge_cfg.temperature
            )
        except Exception as exc:
            _fail_setup(
                "cannot build the live judge transport (need "
                f"GOOGLE_CLOUD_PROJECT/GOOGLE_CLOUD_LOCATION): {exc}"
            )
    templates = [item.strip() for item in args.templates.split(",") if item.strip()]
    cases = [
        case
        for case in expand_cases(
            load_all_stories(REPO_ROOT / "dataset" / "stories"),
            load_expected(REPO_ROOT / "dataset" / "expected"),
        )
        if case.story.template in templates
        and (args.scenario is None or case.expected.scenario == args.scenario)
    ]
    if not cases:
        _fail_setup(f"no dataset cases match templates={templates}")

    case_dir = ARTIFACTS_DIR / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    failed = 0
    try:
        for case in cases:
            case_id = case.case_id.replace("/", "_")
            error_message = None
            try:
                capture = run_case(case, transports)
                failures = evaluate_case(capture, case.expected)
                status = "failed" if failures else "passed"
            except CaseFailure as exc:
                capture, failures, status = None, [], "error"
                error_message = str(exc)
                print(f"ERROR {case.case_id}: {exc}", file=sys.stderr)
            except Exception as exc:  # never abort the suite on one case
                capture, failures, status = None, [], "error"
                error_message = f"{type(exc).__name__}: {exc}"
                print(f"ERROR {case.case_id}: {error_message}", file=sys.stderr)
            if status != "passed":
                failed += 1
            judge_section = _maybe_judge(
                args, judge_cfg, judge_transport, status, capture, case
            )
            if judge_section and judge_section.get("status") != "passed":
                status = "failed"
                failed += 1
            artifact = {
                "case_id": case.case_id,
                "status": status,
                "failures": [
                    {"assertion": f.assertion, "detail": f.detail}
                    for f in failures
                ],
                "capture": capture.model_dump(mode="json") if capture else None,
                "error": error_message if status == "error" else None,
                "judge": judge_section,
            }
            (case_dir / f"{case_id}.json").write_text(
                json.dumps(artifact, indent=2), encoding="utf-8"
            )
            marker = "PASS" if status == "passed" else status.upper()
            print(f"{marker} {case.case_id}")
            for failure in failures:
                print(f"  FAIL {failure.assertion}: {failure.detail}")
            results.append(artifact)
    finally:
        http.close()
        artifacts.close()

    summary = {
        "label": getattr(args, "label", None) or "run",
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "templates": templates,
        "results": [
            {
                "case_id": item["case_id"],
                "status": item["status"],
                "failures": item["failures"],
                "judge": item["judge"],
            }
            for item in results
        ],
    }
    (ARTIFACTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    append_trend(ARTIFACTS_DIR, summary)
    print(
        f"evaluation: {summary['passed']}/{summary['total']} passed "
        f"(artifacts: {ARTIFACTS_DIR})"
    )
    return 1 if failed else 0


def _maybe_judge(args, judge_cfg, judge_transport, status, capture, case) -> dict | None:
    """One judge call when this case is judge-eligible (passed + requested)."""
    if status != "passed" or judge_transport is None or capture is None:
        return None
    smoke_only_clean = getattr(args, "smoke", False) and not getattr(
        args, "judge", False
    )
    if smoke_only_clean and capture.scenario != "clean":
        return None
    if judge_cfg is None:
        judge_cfg = load_judge_config(Path(args.config))
    return run_judge_for_case(
        capture=capture,
        expected=case.expected,
        prompt_text=judge_cfg.prompt_text,
        judge_model=judge_cfg.model,
        prompt_sha256=judge_cfg.judge_md_sha256,
        transport=judge_transport,
    )


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
    parser.add_argument(
        "--templates",
        default="t1",
        help="comma-separated dataset templates to run (default: t1 cheap subset)",
    )
    parser.add_argument("--scenario", default=None, help="run one scenario only")
    parser.add_argument(
        "--artifact-url", default=DEFAULT_ARTIFACT_URL, help="artifact MCP base URL"
    )
    parser.add_argument(
        "--orchestration-dsn",
        default=DEFAULT_ORCHESTRATION_DSN,
        help="read-only orchestration Postgres DSN (agent_runs evidence)",
    )
    parser.add_argument(
        "--facilitator-dsn",
        default=DEFAULT_FACILITATOR_DSN,
        help="read-only facilitator Postgres DSN (ADK event evidence)",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="run one live judge call per deterministic-passing case (spends tokens)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="smoke set: deterministic suite + judge only on the clean case",
    )
    parser.add_argument(
        "--label", default=None, help="run label recorded in the trend report"
    )
    args = parser.parse_args(argv)

    # Config validity (incl. judge prompt SHA) is a precondition of everything.
    load_judge_config(args.config)

    if args.judge_smoke:
        return judge_smoke(Path(args.config), ARTIFACTS_DIR, EVAL_DIR)

    return run_deterministic_suite(args)


if __name__ == "__main__":
    raise SystemExit(main())
