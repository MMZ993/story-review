"""Strict models for the scenario-canonical expected-file contract.

One expected file per scenario (``dataset/expected/<scenario>.json``, D9
amendment 2). The loader expands each to per-template test cases. Fields
split into:

- deterministic fields the Phase 9 runner asserts mechanically
  (delegation decision, outcome, state, produced artifact types+versions,
  po_script exactly-one-of, final state incl. facilitator_turn_count);
- semantic fields consumed by the judge (``semantic_notes``, finding and
  conflict stubs with ``topic``).

Vocabulary (TurnOutcome, SessionState, ArtifactType, Format, Perspective,
StoryId) is reused from the Phase 2 ``review_schemas`` package — the
expected contract speaks the design's language; it is not itself a Phase 2
model.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from review_schemas import ArtifactType, Format, SessionState, TurnOutcome

Severity = Literal["info", "minor", "major", "blocker"]
Invoke = Literal["none", "business", "engineering", "both"]

ScenarioKey = Annotated[
    str,
    StringConstraints(
        pattern=r"^(clean|business-weak|engineering-weak|conflicting"
        r"|partial-resolution|unresolvable|hidden-conflict)$"
        r"|^(comments-benign|comments-clarify-business"
        r"|comments-complete-engineering)$"
    ),
]
FindingKey = Annotated[str, StringConstraints(pattern=r"^[BE]-[1-9][0-9]*$")]
ConflictKey = Annotated[str, StringConstraints(pattern=r"^C-[1-9][0-9]*$")]


class PoTurn(BaseModel):
    """One scripted PO action: exactly one of message or acceptance
    (mirrors the TurnRequest contract in schemas.md)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    message: str | None = None
    po_accepted: bool = False

    @model_validator(mode="after")
    def exactly_one_action(self):
        if (self.message is not None) == self.po_accepted:
            raise ValueError(
                "PO turns contain exactly one message or acceptance action"
            )
        return self


class DelegationExpectation(BaseModel):
    """Deterministic subset of DelegationDecision the dataset pins.

    Unresolvable dialogue turns pin ONLY ``open_issues_empty`` (routing is
    the facilitator's adaptive choice there) — hence all fields optional.
    Omitted fields are "not asserted", not "must be absent".
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    invoke: Invoke | None = None
    reuse_previous: bool | None = None
    extra_context_expected: bool | None = None
    open_issues_empty: bool | None = None


class ProducedArtifact(BaseModel):
    """Artifact type + version expected on a turn; versions are per
    (story_run, type) per schemas.md lineage rules."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: ArtifactType
    version: int = Field(ge=1)


class ExpectedTurn(BaseModel):
    """One dialogue turn's expected transition (turn 1 = opening)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    turn_number: int = Field(ge=1)
    outcome: TurnOutcome
    state_after: SessionState
    delegation: DelegationExpectation | None = None
    #: Pinned list = the exact (type, version) set the turn must produce
    #: ([] asserts nothing was produced); explicit null = unpinned (the
    #: turn's artifact set is free; version continuity is asserted instead).
    produced_artifacts: list[ProducedArtifact] | None = Field(default_factory=list)
    semantic_notes: str = ""

    @model_validator(mode="after")
    def validate_turn(self):
        expected_state = {
            "continue": "active",
            "park": "parked",
            "finalize": "completed",
        }[self.outcome]
        if self.state_after != expected_state:
            raise ValueError("state_after does not match outcome")
        if (
            self.produced_artifacts is not None
            and any(
                a.type.startswith("report-") for a in self.produced_artifacts
            )
            and self.outcome != "finalize"
        ):
            raise ValueError("reports are produced only on finalize turns")
        if self.delegation is None and self.outcome != "finalize":
            raise ValueError("delegation is required unless the turn finalizes")
        return self


class FindingStub(BaseModel):
    """Semantic finding requirement: runtime finding IDs are
    reviewer-assigned and never pinned; presence is judge-matched."""

    model_config = ConfigDict(extra="forbid", strict=True)

    key: FindingKey
    min_severity: Severity
    topic: str = Field(min_length=1)
    appears_in_version: int = Field(ge=1)
    resolved_at_turn: int | None = Field(default=None, ge=2)


class PerspectiveFindings(BaseModel):
    """Per-perspective expectations: severity ceiling + required stubs."""

    model_config = ConfigDict(extra="forbid", strict=True)

    max_severity: Severity
    required: list[FindingStub] = Field(default_factory=list)


class ConflictStub(BaseModel):
    """Semantic conflict requirement (C-n pattern per schemas.md)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    key: ConflictKey
    kind: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    first_seen_turn: int | None = Field(default=None, ge=1)
    resolved_at_turn: int | None = Field(default=None, ge=2)
    deterministically_pinned: bool = True


class ExpectedConflicts(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    at_turn_1: list[ConflictStub] = Field(default_factory=list)
    later: list[ConflictStub] = Field(default_factory=list)
    note: str = ""


class ExpectedFinal(BaseModel):
    """Final session state and finalized-review/report expectations."""

    model_config = ConfigDict(extra="forbid", strict=True)

    state: SessionState
    final_turn_number: int = Field(ge=1)
    facilitator_turn_count: int = Field(ge=0, le=10)
    finalized: bool = True
    po_accepted: bool = False
    remaining_open_issues_empty: bool = True
    reports: list[Format] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_final(self):
        if self.state == "completed":
            if not self.finalized:
                raise ValueError("completed sessions are finalized")
        elif self.finalized or self.reports:
            raise ValueError(
                "only completed sessions have a finalized review and reports"
            )
        if self.po_accepted and not self.finalized:
            raise ValueError("acceptance is a finalize-path event")
        if self.po_accepted and not self.remaining_open_issues_empty:
            raise ValueError("acceptance cannot retain open issues")
        return self


class ExpectedCase(BaseModel):
    """One scenario-canonical expected-file contract."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    scenario: ScenarioKey
    requested_formats: list[Format] = Field(min_length=1, max_length=2)
    po_script: list[PoTurn] = Field(min_length=1, max_length=10)
    expected_turns: list[ExpectedTurn] = Field(min_length=1, max_length=11)
    expected_findings: dict[str, PerspectiveFindings] = Field(
        default_factory=dict
    )
    expected_conflicts: ExpectedConflicts | None = None
    expected_final: ExpectedFinal
    invariance: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self):
        expected_scenarios_views = {
            "review-business",
            "review-engineering",
        }
        if set(self.expected_findings) != expected_scenarios_views:
            raise ValueError(
                "expected_findings must carry both review perspectives"
            )
        for name, view in self.expected_findings.items():
            prefix = "B-" if name == "review-business" else "E-"
            if any(not stub.key.startswith(prefix) for stub in view.required):
                raise ValueError(
                    "finding stub prefix does not match its perspective"
                )
        numbers = [t.turn_number for t in self.expected_turns]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("turn numbers must be contiguous from 1")
        if len(self.po_script) != len(self.expected_turns) - 1:
            raise ValueError(
                "expected_turns = opening turn + one entry per PO turn"
            )
        final = self.expected_final
        last = self.expected_turns[-1]
        if final.state != last.state_after or (
            final.final_turn_number != last.turn_number
        ):
            raise ValueError("expected_final does not match the last turn")
        if final.state == "completed" and (
            set(final.reports) != set(self.requested_formats)
        ):
            raise ValueError(
                "completed sessions render exactly the requested report formats"
            )
        if self.expected_conflicts is not None and (
            self.expected_conflicts.at_turn_1 or self.expected_conflicts.later
        ):
            conflict_turn_1 = self.expected_turns[0]
            if conflict_turn_1.delegation is not None and (
                conflict_turn_1.delegation.open_issues_empty
            ):
                raise ValueError(
                    "a turn-1 conflict requires non-empty open issues"
                )
        return self
