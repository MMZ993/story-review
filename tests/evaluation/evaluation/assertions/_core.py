"""Shared internals of the deterministic assertion battery (inc 1).

``AssertionFailure`` is the battery's failure record; ``_turn_view``
locates one persisted TurnView in a capture. Severity ranking is
re-exported from ``capture`` so content assertions speak the same
ordering as the capture models.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.capture import severity_rank  # re-export; noqa: F401


@dataclass
class AssertionFailure:
    """One failed deterministic assertion (assertion id + evidence)."""

    assertion: str
    detail: str


def _turn_view(capture, turn_number: int) -> dict | None:
    for turn in capture.turns:
        if turn.get("turn_number") == turn_number:
            return turn
    return None
