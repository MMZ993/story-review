"""Typed capture of one evaluation case's observable behavior (inc 1).

Everything the deterministic assertions consume: the persisted turn view,
final session detail, artifact contents keyed ``type#vN``, the audit
``agent_runs`` rows (with real invocation spans since the flows record
them), facilitator-initiated MCP tool-call names, and the persistence
probes. Pure data — populated by ``case_runner`` over real
HTTP/DB transports, faked in unit tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "minor", "major", "blocker"]

#: Severity ordering used by the findings-ceiling assertion.
SEVERITY_RANK = {"info": 0, "minor": 1, "major": 2, "blocker": 3}


def severity_rank(severity: str) -> int:
    """Rank of a severity name; unknown names rank above blocker (fail loud)."""
    return SEVERITY_RANK.get(severity, len(SEVERITY_RANK))


def artifact_key(artifact_type: str, version: int) -> str:
    """Content-map key for one artifact version."""
    return f"{artifact_type}#v{version}"


class AgentRunEvidence(BaseModel):
    """One ``agent_runs`` audit row relevant to a case (local mode)."""

    agent: str
    agent_version: str
    prompt_sha256: str
    state: str
    transport_attempts: int
    corrective_reprompts: int
    started_at: datetime
    finished_at: datetime


class PersistenceEvidence(BaseModel):
    """Post-terminal persistence probes for one case.

    - ``restore_ok``: GET /sessions/{id} after the final turn returns the
      persisted terminal state (session restore works);
    - ``same_run_read_ok``: reading this run's latest synthesis artifact
      through the artifact MCP succeeds (same-run lineage reads);
    - ``cross_run_rejected``: reading that artifact under a foreign
      story_run_id is rejected (run-scoped reads).
    """

    restore_ok: bool
    restore_state: str | None = None
    same_run_read_ok: bool = False
    cross_run_rejected: bool = False
    notes: list[str] = Field(default_factory=list)


class CaseCapture(BaseModel):
    """All deterministic observations for one executed case."""

    case_id: str
    scenario: str
    template: str
    story_id: str
    session_id: str
    story_run_id: str
    # Persisted TurnView per turn (turn 1 = opening), raw JSON dicts.
    turns: list[dict] = Field(default_factory=list)
    # Final SessionDetail raw JSON (state, counts, reports, references).
    final_detail: dict = Field(default_factory=dict)
    # Artifact contents keyed "type#vN" (raw JSON content).
    artifacts: dict[str, dict] = Field(default_factory=dict)
    agent_runs: list[AgentRunEvidence] = Field(default_factory=list)
    # Facilitator-initiated MCP tool-call names observed in the ADK
    # session-event trace, in first-seen order.
    facilitator_tool_calls: list[str] = Field(default_factory=list)
    persistence: PersistenceEvidence | None = None
