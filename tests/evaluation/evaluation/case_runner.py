"""Case runner: replays one dataset case over real HTTP (increment 1).

Replays the expected file's ``po_script`` verbatim against the compose
orchestration API (opening turn = flow-1 create; each script entry = one
turn; ``po_accepted: true`` is the acceptance turn), then captures the
persisted session view, every artifact version's content, the audit
``agent_runs`` rows, the facilitator MCP tool-call trace, and the
persistence probes. Judge OFF — deterministic only.

Transport dependencies are injected (``Transports``) so unit tests drive
the runner with fakes and live runs pass real clients.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

import httpx
from dataset_loader.dataset import TestCase
from evaluation.artifact_client import ArtifactClientError, ArtifactToolFailure
from evaluation.capture import (
    CaseCapture,
    PersistenceEvidence,
    artifact_key,
)
from evaluation.orchestration_client import OrchestrationClient, OrchestrationError


class CaseFailure(Exception):
    """The case could not be executed to a terminal state (not an
    assertion verdict — a transport/HTTP-level failure with evidence)."""


class ArtifactReader(Protocol):
    def get_artifact(self, artifact_id: str, story_run_id: str) -> dict: ...


@dataclass
class Transports:
    """Everything the runner needs, injected for testability."""

    http: OrchestrationClient
    artifacts: ArtifactReader
    fetch_agent_runs: Callable[[str, str], list]
    fetch_facilitator_tool_calls: Callable[[str, str], list[str]]
    orchestration_dsn: str
    facilitator_dsn: str


def run_case(case: TestCase, transports: Transports) -> CaseCapture:
    """Execute one case and capture all deterministic observations."""
    http = transports.http
    expected = case.expected
    try:
        created = http.create_session(
            case.story.story_id, list(expected.requested_formats)
        )
        session_id = created["session_id"]
        story_run_id = created["story_run_id"]
        for step in expected.po_script:
            body = (
                {"message": step.message, "po_accepted": False}
                if step.message is not None
                else {"message": None, "po_accepted": True}
            )
            http.post_turn(session_id, body)
        detail = http.get_session(session_id)
    except OrchestrationError as exc:
        raise CaseFailure(f"{case.case_id}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise CaseFailure(f"{case.case_id}: transport failure: {exc}") from exc

    artifacts = _read_artifacts(transports, detail)
    try:
        agent_runs = transports.fetch_agent_runs(
            transports.orchestration_dsn, session_id
        )
        tool_calls = transports.fetch_facilitator_tool_calls(
            transports.facilitator_dsn, session_id
        )
    except Exception as exc:  # DB evidence path down = case error, not abort
        raise CaseFailure(f"{case.case_id}: evidence query failed: {exc}") from exc
    persistence = _probe_persistence(
        transports, session_id, detail, artifacts, case.case_id
    )
    return CaseCapture(
        case_id=case.case_id,
        scenario=case.expected.scenario,
        template=case.story.template,
        story_id=case.story.story_id,
        session_id=session_id,
        story_run_id=story_run_id,
        turns=detail.get("turns", []),
        final_detail=detail,
        artifacts=artifacts,
        agent_runs=agent_runs,
        facilitator_tool_calls=tool_calls,
        persistence=persistence,
    )


def _read_artifacts(transports: Transports, detail: dict) -> dict[str, dict]:
    """Every artifact version of the run, keyed ``type#vN``."""
    contents: dict[str, dict] = {}
    for reference in detail.get("artifact_references", []):
        key = artifact_key(reference["type"], reference["version"])
        if key in contents:
            continue
        try:
            payload = transports.artifacts.get_artifact(
                reference["artifact_id"], reference["story_run_id"]
            )
        except (ArtifactClientError, ArtifactToolFailure) as exc:
            raise CaseFailure(f"artifact read {key} failed: {exc}") from exc
        contents[key] = payload.get("content", payload)
    return contents


def _probe_persistence(
    transports: Transports,
    session_id: str,
    detail: dict,
    artifacts: dict[str, dict],
    case_id: str,
) -> PersistenceEvidence:
    """Restore + same-run read + cross-run rejection probes (no model calls)."""
    notes: list[str] = []
    try:
        restored = transports.http.get_session(session_id)
        restore_ok = restored.get("state") == detail.get("state")
        restore_state = restored.get("state")
    except OrchestrationError as exc:
        notes.append(f"restore failed: {exc}")
        restore_ok, restore_state = False, None

    same_run_ok = False
    cross_run_rejected = False
    synthesis_refs = [
        ref
        for ref in detail.get("artifact_references", [])
        if ref["type"] == "synthesis"
    ]
    if synthesis_refs:
        latest = max(synthesis_refs, key=lambda ref: ref["version"])
        try:
            transports.artifacts.get_artifact(
                latest["artifact_id"], latest["story_run_id"]
            )
            same_run_ok = True
        except (ArtifactClientError, ArtifactToolFailure) as exc:
            notes.append(f"same-run read failed: {exc}")
        foreign_run = f"run-{uuid.uuid4()}"
        try:
            transports.artifacts.get_artifact(latest["artifact_id"], foreign_run)
            notes.append("cross-run read unexpectedly succeeded")
        except ArtifactToolFailure:
            cross_run_rejected = True
        except ArtifactClientError as exc:
            notes.append(f"cross-run read raised transport error: {exc}")
    else:
        notes.append(f"{case_id}: no synthesis artifact to probe")

    return PersistenceEvidence(
        restore_ok=restore_ok,
        restore_state=restore_state,
        same_run_read_ok=same_run_ok,
        cross_run_rejected=cross_run_rejected,
        notes=notes,
    )
