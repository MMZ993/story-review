"""Aggregate trend report across evaluation runs (Phase 9 increment 3).

Every runner execution appends one typed entry to
``artifacts/trend.json`` (a JSON array — the audit trail of the tuning
loop) and re-renders ``artifacts/trend.md`` (the human summary: latest
run verdicts, pass rates, per-case judge scores, failure counts over
time). Pure file handling — no model calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

TREND_JSON = "trend.json"
TREND_MD = "trend.md"


def load_trend(artifacts_dir: Path) -> list[dict]:
    """Load the trend history (empty list when none exists yet)."""
    path = artifacts_dir / TREND_JSON
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def append_trend(artifacts_dir: Path, run_summary: dict) -> None:
    """Stamp one run summary with its UTC timestamp and append it."""
    runs = load_trend(artifacts_dir)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **run_summary,
    }
    runs.append(entry)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / TREND_JSON).write_text(
        json.dumps(runs, indent=2), encoding="utf-8"
    )
    (artifacts_dir / TREND_MD).write_text(render_trend_md(runs), encoding="utf-8")


def _judge_scores(judge: dict | None) -> str:
    """Render one case's judge scores as ``dim=n`` pairs (or a dash)."""
    if not judge or not judge.get("result"):
        return "-"
    scores = judge["result"].get("scores", [])
    return " ".join(f"{s['dimension'].split('-')[0]}={s['score']}" for s in scores)


def render_trend_md(runs: list[dict]) -> str:
    """Render the markdown trend summary for the whole history."""
    lines = ["# Evaluation trend", ""]
    for run in runs:
        results = run.get("results", [])
        det_pass = sum(1 for r in results if r["status"] == "passed")
        judged = [r for r in results if (r.get("judge") or {}).get("result")]
        judge_pass = sum(
            1 for r in judged if r["judge"]["result"].get("passed")
        )
        lines.append(
            f"## {run.get('label', run['timestamp'])} — {run['timestamp']} "
            f"(templates: {','.join(run.get('templates', []))})"
        )
        lines.append("")
        lines.append(
            f"deterministic {det_pass}/{len(results)} · "
            f"judged {judge_pass}/{len(judged)}"
        )
        lines.append("")
        lines.append("| case | status | failures | judge |")
        lines.append("|---|---|---|---|")
        for r in results:
            judge = r.get("judge") or {}
            judge_col = (
                f"{judge.get('status', '-')} ({_judge_scores(judge)})"
                if judge
                else "-"
            )
            lines.append(
                f"| {r['case_id']} | {r['status']} | "
                f"{len(r.get('failures', []))} | {judge_col} |"
            )
        lines.append("")
        for r in results:
            for failure in r.get("failures", []):
                lines.append(
                    f"- {r['case_id']}: {failure['assertion']}: "
                    f"{failure['detail']}"
                )
            for tolerated in r.get("tolerated", []):
                lines.append(
                    f"- (tolerated) {r['case_id']}: {tolerated}"
                )
        lines.append("")
    return "\n".join(lines)
