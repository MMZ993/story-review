"""Trend report unit tests (Phase 9 increment 3)."""

from __future__ import annotations

import json

from evaluation.trend import append_trend, load_trend, render_trend_md


def make_run(label="run-6", templates=("t1",)):
    return {
        "label": label,
        "templates": list(templates),
        "results": [
            {
                "case_id": "t1/clean",
                "status": "passed",
                "failures": [],
                "judge": {"status": "passed", "result": {"passed": True,
                    "scores": [{"dimension": d, "score": 4} for d in (
                        "review-coverage", "grounding", "conflict-resolution",
                        "delegation", "final-state")]}},
            },
            {"case_id": "t1/conflicting", "status": "failed",
             "failures": [{"assertion": "conflict[C-1].present",
                           "detail": "synthesis v1 conflicts: []"}],
             "judge": None},
        ],
    }


def test_append_and_load_trend(tmp_path):
    append_trend(tmp_path, make_run("run-6"))
    append_trend(tmp_path, make_run("run-7"))
    runs = load_trend(tmp_path)
    assert [r["label"] for r in runs] == ["run-6", "run-7"]
    # each entry is stamped with a UTC timestamp
    assert runs[0]["timestamp"].endswith("Z")


def test_render_trend_md_summarizes_latest_and_progress(tmp_path):
    append_trend(tmp_path, make_run("run-6"))
    markdown = render_trend_md(load_trend(tmp_path))
    assert "run-6" in markdown
    assert "t1/clean" in markdown
    assert "conflict[C-1].present" in markdown
    # aggregate: latest run deterministic pass rate + judged pass rate
    assert "1/2" in markdown
