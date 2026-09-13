"""Agent Engine deployment smoke (Phase 8 increment 3).

Invokes one deployed agent resource with a real Vertex-backed request and
validates the final reply against the strict shared schema — the same
typed-output check the local adapter shells apply (docs/operations/
deployment.md: a release pointer moves only after the unit smoke passes).

Authenticates via impersonated sa-orchestration credentials (the runtime
invoker, roles/aiplatform.user) — proving the exact principal the deployed
orchestration will use.

Usage (repo root, after `source infra/envs/home.env`):
  RESOURCE="projects/$PROJECT_ID/locations/$REGION/reasoningEngines/<id>" \
  uv run --no-project --with google-cloud-aiplatform \
    --with-editable shared/review_schemas --with-editable shared/agent_kit \
    python deploy/agents/smoke.py <slug>

Exit codes: 0 pass, 1 smoke failure, 2 bad input.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

slug = sys.argv[1] if len(sys.argv) > 1 else ""
resource = os.environ.get("RESOURCE", "")
if slug not in {
    "facilitator",
    "business-reviewer",
    "engineering-reviewer",
    "synthesis",
} or not resource:
    print("usage: smoke.py <slug> with RESOURCE= env", file=sys.stderr)
    raise SystemExit(2)


def _review(perspective: str, story_id: str) -> Any:
    from review_schemas import ReviewReport

    prefix = "B-" if perspective == "business" else "E-"
    return ReviewReport(
        perspective=perspective,
        story_id=story_id,
        summary=f"{perspective} summary of {story_id}.",
        findings=[
            {
                "id": f"{prefix}1",
                "title": "Gap found",
                "description": "The story misses an important case.",
                "severity": "minor",
                "category": "completeness",
            }
        ],
        risks=[],
        questions_for_po=["Which rate limit applies?"],
    )


def _ref(artifact_id: str, type_: str, perspective: str | None, run: str):
    from datetime import UTC, datetime

    from review_schemas import ArtifactReference

    return ArtifactReference(
        artifact_id=artifact_id,
        story_run_id=run,
        type=type_,
        perspective=perspective,
        version=1,
        created_at=datetime.now(UTC),
        content_type="application/json",
        checksum_sha256="a" * 64,
    )


def _synthesis(story_id: str, run: str):
    from review_schemas import SynthesisReport

    return SynthesisReport(
        story_id=story_id,
        summary="Two findings need PO input.",
        merged_findings=[
            {
                "id": "B-1",
                "title": "Gap found",
                "description": "The story misses an important case.",
                "severity": "minor",
                "category": "completeness",
            }
        ],
        conflicts=[],
        questions_for_po=["Which rate limit applies?"],
        inputs={
            "business": _ref("art-00000000-0000-4000-8000-0000000000b1", "review-business", "business", run),
            "engineering": _ref(
                "art-00000000-0000-4000-8000-0000000000e1", "review-engineering", "engineering", run
            ),
        },
    )


def _message(slug: str) -> str:
    """A minimal but schema-valid invocation input per agent, rendered with
    the same agent_kit renderers the local adapters use."""
    from agent_kit.facilitator_input import FacilitatorRequest, render_facilitator_message
    from agent_kit.reviewer_input import ReviewerRequest, render_reviewer_message
    from agent_kit.synthesis_input import PerspectivePair, SynthesisRequest, render_synthesis_message
    from review_schemas import StoryDetail

    story_id = "story-01"
    run = "run-00000000-0000-4000-8000-000000000001"
    story = StoryDetail(
        story_id=story_id,
        title="Story 01",
        status="New",
        description="As a user I want a feature so that value flows.",
        acceptance_criteria=["Given a story when reviewed then findings appear."],
        epic_context="Epic 3 - reporting.",
        roadmap_context="Q3 reporting milestone.",
    )
    if slug in ("business-reviewer", "engineering-reviewer"):
        return render_reviewer_message(ReviewerRequest(story=story))
    if slug == "synthesis":
        return render_synthesis_message(
            SynthesisRequest(
                business=PerspectivePair(
                    report=_review("business", story_id),
                    reference=_ref(
                        "art-00000000-0000-4000-8000-0000000000b1", "review-business", "business", run
                    ),
                ),
                engineering=PerspectivePair(
                    report=_review("engineering", story_id),
                    reference=_ref(
                        "art-00000000-0000-4000-8000-0000000000e1",
                        "review-engineering",
                        "engineering",
                        run,
                    ),
                ),
            )
        )
    # facilitator: an opening turn (turn 1, no PO message)
    request = FacilitatorRequest(
        session_id="sess-00000000-0000-4000-8000-000000000001",
        turn_number=1,
        invocation_id="00000000-0000-4000-8000-000000000001",
        synthesis_report=_synthesis(story_id, run),
        synthesis_reference=_ref("art-00000000-0000-4000-8000-000000000051", "synthesis", None, run),
    )
    return render_facilitator_message(request)


def _validate(slug: str, text: str) -> None:
    """Parse the final reply as JSON and validate it with the strict shared
    schema for the agent (fail-loud — smoke = schema-valid typed output)."""
    from review_schemas import FacilitatorTurnOutput, ReviewReport, SynthesisReport

    if slug in ("business-reviewer", "engineering-reviewer"):
        report = ReviewReport.model_validate_json(text)
        assert report.perspective == slug.removesuffix("-reviewer")
        print(f"validated ReviewReport: {report.perspective}, {len(report.findings)} findings")
    elif slug == "synthesis":
        report = SynthesisReport.model_validate_json(text)
        print(f"validated SynthesisReport: {len(report.merged_findings)} findings")
    else:
        output = FacilitatorTurnOutput.model_validate_json(text)
        print(f"validated FacilitatorTurnOutput: invoke={output.delegation.invoke}")


def main() -> int:
    import google.auth
    import google.auth.impersonated_credentials
    import google.auth.transport.requests
    import vertexai

    project = os.environ["PROJECT_ID"]
    region = os.environ.get("REGION", "europe-west4")
    target = f"sa-orchestration@{project}.iam.gserviceaccount.com"

    source, _ = google.auth.default()
    creds = google.auth.impersonated_credentials.Credentials(
        source_credentials=source,
        target_principal=target,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(google.auth.transport.requests.Request())

    client = vertexai.Client(project=project, location=region, credentials=creds)
    engine = client.agent_engines.get(name=resource)
    print(f"engine: {engine.api_resource.name} (display: {engine.api_resource.display_name})")

    kwargs: dict[str, Any] = {"message": _message(slug), "user_id": "smoke"}
    session_id: str | None = None
    if slug == "facilitator":
        session = engine.create_session(user_id="smoke")
        session_id = session["id"]
        kwargs["session_id"] = session_id
        print(f"session: {session_id}")

    try:
        final_text = ""
        for event in engine.stream_query(**kwargs):
            if isinstance(event, dict) and event.get("content") and event.get(
                "author", "facilitator" if slug == "facilitator" else None
            ) not in ("user", None):
                parts = event["content"].get("parts", [])
                for part in parts:
                    if isinstance(part, dict) and part.get("text"):
                        final_text = part["text"]
    finally:
        # smoke sessions are disposable — do not leave rows in the
        # Cloud SQL facilitator session store
        if session_id is not None:
            engine.delete_session(user_id="smoke", session_id=session_id)

    if not final_text.strip():
        print("FAIL: no final text in the stream", file=sys.stderr)
        return 1
    _validate(slug, final_text)
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
