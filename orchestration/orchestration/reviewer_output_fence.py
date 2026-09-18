"""Reviewer output fence (D35, docs/design/data-flow.md).

A pure deterministic post-processing step over a reviewer's
`ReviewReport` plus the invocation inputs (story text, previous review,
extra context) — no I/O, no model calls — applied at both reviewer
invocation points before the report is persisted. It makes two
stochastic severity failure classes deterministic:

1. **Scope-settlement invalidation**: a finding whose content words
   materially overlap a story sentence that explicitly settles a matter
   ("out of scope", "no additional", "exactly", ...) is invalid and is
   dropped.
2. **Re-review downgrade clamp**: in a re-review made with extra
   context, a finding that matches a previous finding *and* overlaps the
   extra context is clamped one severity level below the *previous*
   finding's severity (an already-`info` match is dropped).

"Material overlap" is operationalized as the overlap coefficient
(|A ∩ B| / min(|A|, |B|)) over content-word token sets; thresholds are
calibrated against the recorded Phase 9 evaluation captures (see
orchestration/tests/test_reviewer_output_fence.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from review_schemas.review import Finding, ReviewReport, StoryDetail

#: Embedded small English stopword list (kept local so the fence stays a
#: pure, dependency-free function).
_STOPWORDS = frozenset(
    """the a an and or of to in on for with by is are was were be been
    it its this that these those as at from not no but if then than so
    such can could should would will may might must do does did have has
    had their there when which who whom what where how all any each other
    more most some only own same too very just also into over under again
    further once you your our""".split()
)

#: Scope-settlement markers from the D35 design (lowercase substrings).
_SETTLEMENT_MARKERS = (
    "out of scope",
    "no additional",
    "exactly",
    "handled by the existing",
    "not in scope",
    "excluded",
    "no story-specific",
)

#: Overlap coefficient at/above which a finding matches a settling
#: clause (Rule 1) or a previous finding (Rule 2). Calibrated: fires on
#: the t1_clean capture B-1 finding at 0.50.
_MATCH_THRESHOLD = 0.35

#: Overlap coefficient at/above which a Rule 2 finding overlaps the
#: extra context. Calibrated down from the design sketch's 0.25 to 0.20
#: so the clamp fires on the t1_engineering-weak capture (extra context
#: is a 13-token sentence; 0.25 would never fire on it).
_CONTEXT_THRESHOLD = 0.20

#: One severity level below, per Rule 2; `info` findings are dropped.
_DOWNGRADE = {"blocker": "major", "major": "minor", "minor": "info"}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_TOKEN_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class FenceEvent:
    """One auditable fence action (drop or clamp of one finding)."""

    rule: str  # "scope_settlement" | "re_review_clamp"
    finding_id: str
    reference: str  # settling clause text or previous finding id
    similarity: float


def story_plain_text(story: StoryDetail) -> str:
    """The story's reviewable prose: description, acceptance criteria,
    and all comment texts, joined with spaces. HTML tags are replaced by
    a space (entities are left as-is); title and epic/roadmap context
    are excluded — Rule 1 fires on story-body settlement sentences."""
    parts = [story.description, *story.acceptance_criteria]
    parts += [comment.text for comment in story.comments]
    return " ".join(_HTML_TAG_RE.sub(" ", part) for part in parts)


def _content_tokens(text: str) -> frozenset[str]:
    """Content-word token set: lower-cased alphanumeric tokens of >= 3
    chars minus the embedded stopword list."""
    return frozenset(
        token
        for token in _TOKEN_RE.split(text.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    )


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Overlap coefficient |A ∩ B| / min(|A|, |B|); 0.0 on empty sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _settling_clauses(story_text: str) -> list[str]:
    """Sentences of the story text that contain a settlement marker."""
    return [
        sentence
        for sentence in _SENTENCE_RE.split(story_text)
        if any(marker in sentence.lower() for marker in _SETTLEMENT_MARKERS)
    ]


def _finding_tokens(finding: Finding) -> frozenset[str]:
    """Content-word tokens of a finding's title + description."""
    return _content_tokens(f"{finding.title} {finding.description}")


def _apply_scope_settlement(
    findings: list[Finding], clauses: list[list[str]]
) -> tuple[list[Finding], list[FenceEvent]]:
    """Rule 1: drop findings materially overlapping a settling clause."""
    kept: list[Finding] = []
    events: list[FenceEvent] = []
    for finding in findings:
        tokens = _finding_tokens(finding)
        for clause_text, clause_tokens in clauses:
            similarity = _overlap(tokens, clause_tokens)
            if similarity >= _MATCH_THRESHOLD:
                events.append(
                    FenceEvent(
                        rule="scope_settlement",
                        finding_id=finding.id,
                        reference=clause_text,
                        similarity=round(similarity, 4),
                    )
                )
                break
        else:
            kept.append(finding)
    return kept, events


def _apply_re_review_clamp(
    findings: list[Finding],
    previous_review: ReviewReport,
    extra_context: str,
) -> tuple[list[Finding], list[FenceEvent]]:
    """Rule 2: clamp findings matching both a previous finding and the
    extra context to one severity below the previous severity (drop if
    the previous finding was already `info`)."""
    previous = [
        (finding, _finding_tokens(finding)) for finding in previous_review.findings
    ]
    context_tokens = _content_tokens(extra_context)
    kept: list[Finding] = []
    events: list[FenceEvent] = []
    for finding in findings:
        tokens = _finding_tokens(finding)
        match = max(
            (
                (prev, similarity, _overlap(tokens, context_tokens))
                for prev, prev_tokens in previous
                if (similarity := _overlap(tokens, prev_tokens)) >= _MATCH_THRESHOLD
            ),
            key=lambda m: m[1],
            default=None,
        )
        if match is not None and match[2] >= _CONTEXT_THRESHOLD:
            prev, similarity, _ = match
            events.append(
                FenceEvent(
                    rule="re_review_clamp",
                    finding_id=finding.id,
                    reference=prev.id,
                    similarity=round(similarity, 4),
                )
            )
            if prev.severity == "info":
                continue  # already at the floor: drop
            finding = finding.model_copy(
                update={"severity": _DOWNGRADE[prev.severity]}
            )
        kept.append(finding)
    return kept, events


def apply_fence(
    report: ReviewReport,
    *,
    story_text: str,
    previous_review: ReviewReport | None = None,
    extra_context: str | None = None,
) -> tuple[ReviewReport, list[FenceEvent]]:
    """Run both fence rules over one review report.

    Args:
        report: the reviewer's raw report (never mutated).
        story_text: `story_plain_text` output for the reviewed story.
        previous_review: the prior review for this perspective, when the
            invocation is a re-review (Rule 2 input).
        extra_context: the PO extra context for the re-review, when any
            (Rule 2 fires only when both re-review inputs are present).

    Returns:
        (post-fence report, fence events). The report is rebuilt via
        `model_copy` (and clamped findings re-copied) so every other
        field is preserved exactly; the original report is untouched and
        the same object is returned when no finding changed.
    """
    clauses = [
        (clause, _content_tokens(clause)) for clause in _settling_clauses(story_text)
    ]
    findings, events = _apply_scope_settlement(report.findings, clauses)
    if previous_review is not None and extra_context:
        findings, clamp_events = _apply_re_review_clamp(
            findings, previous_review, extra_context
        )
        events += clamp_events
    if not events:
        return report, events
    return report.model_copy(update={"findings": findings}), events
