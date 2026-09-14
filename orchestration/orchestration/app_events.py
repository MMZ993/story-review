"""FastAPI application events (observability.md "Callbacks and application
events" and "Loop safety and dashboards", Phase 8 increment-6 slice C).

The alertable failure conditions — retry exhaustion and delegation-
validation failure — and the gate/park decisions are emitted as
structured events on the ``storyreview.app`` logger. The JSON handler
(carried by ``configure_logging``) turns each into a Cloud Logging
entry whose ``event`` field the slice-C log-based Cloud Monitoring
metrics filter on; the events double as the dashboard's application
signal layer.

Events (``event`` field): ``retry_exhausted``,
``delegation_validation_failed``, ``gate_decision``, ``session_parked``.
All are side-effect free log calls at the chokepoints — they never
change control flow.
"""

from __future__ import annotations

import logging

#: Logger for application events; child of the JSON-configured
#: ``storyreview`` root so the handler formatting applies.
APP_LOGGER = "storyreview.app"

#: Error codes that mean the shared client's retry budget ran out (the
#: 503 retryable family — ``api_errors.upstream_failure`` is "retry-
#: exhausted upstream or deadline exhaustion").
_RETRY_EXHAUSTED_CODES = frozenset(
    {"UPSTREAM_UNAVAILABLE", "AGENT_CALL_FAILED", "RENDER_FAILED"}
)

#: Error codes that mean the facilitator's corrective re-prompt loop
#: exhausted on a malformed DelegationDecision (observability.md).
_DELEGATION_VALIDATION_CODES = frozenset({"DELEGATION_VALIDATION"})


def log_app_event(event: str, *, level: int = logging.INFO, **fields) -> None:
    """Emit one application event; ``fields`` become structured
    correlation fields on the JSON log line (correlation_id, session_id,
    agent, outcome, ...). Never raises — a telemetry call must not
    change control flow."""
    logging.getLogger(APP_LOGGER).log(
        level, event, extra={"event": event, **fields}
    )


def alert_event_for(error) -> str | None:
    """The alertable application event an API error represents, or None.

    Args: error — a ``review_schemas.errors.ErrorBody``.
    """
    if error.code in _DELEGATION_VALIDATION_CODES:
        return "delegation_validation_failed"
    if error.code in _RETRY_EXHAUSTED_CODES and error.retryable:
        return "retry_exhausted"
    return None


def log_alert_event(error, *, correlation_id: str | None, user_id=None) -> None:
    """Emit the alertable-failure event for one API error, when it is one.

    Called from the ApiError exception handler so every route's failure
    (flows, turns, finalize, abandon) funnels through one chokepoint.
    """
    event = alert_event_for(error)
    if event is not None:
        log_app_event(
            event,
            level=logging.WARNING,
            error_code=error.code,
            error_message=error.message,
            agent=error.agent,
            correlation_id=correlation_id,
            user_id=user_id,
        )


def gate_decision(
    *, outcome: str, facilitator_turn: int, session_id: str, correlation_id
) -> None:
    """One gate evaluation result (continue / finalize / park)."""
    log_app_event(
        "gate_decision",
        outcome=outcome,
        facilitator_turn=facilitator_turn,
        session_id=session_id,
        correlation_id=correlation_id,
    )


def session_parked(
    *, session_id: str, facilitator_turn: int, correlation_id
) -> None:
    """The park transition persisted (turn cap or story-run state)."""
    log_app_event(
        "session_parked",
        session_id=session_id,
        facilitator_turn=facilitator_turn,
        correlation_id=correlation_id,
    )
