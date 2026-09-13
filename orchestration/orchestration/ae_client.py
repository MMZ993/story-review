"""Agent Engine (AE) invocation clients behind the Phase-5 client seams.

Phase 8 increment 4 (D25): the deployed orchestration invokes the four
Agent Engine agents over the raw REST surface proven by the connectivity
spike — ``POST …/reasoningEngines/{id}:streamQuery?alt=sse`` with a
``{classMethod: "async_stream_query", input: {user_id, message,
session_id?}}`` body and an ADC bearer token. The response is
concatenated JSON documents (one per ADK event; ``function_response``
serializes snake_case). The aiplatform SDK is deliberately NOT used: it
would drag the ADK into orchestration and its `stream_query` exposes no
per-attempt timeout, while httpx lets the existing observability.md
transport policies (short 60 s / 3 jittered; facilitator 120 s / 2 fixed
5 s) stay enforceable. Session management rides the documented REST
routes (``POST {engine}/sessions``, ``GET {engine}/sessions?userId=…``,
``GET {engine}/sessions/{id}/events``) — verified live at the increment-4
gate.

Audit fields in AE mode (D25 amendment): `agent_version` is the engine's
deploy label (e.g. ``business-reviewer-7d1b9bd``) and `prompt_sha256`` is
the SHA-256 of the rendered user message (an invocation input fingerprint
— the system prompt is baked inside the engine, invisible here).
`corrective_reprompts` is always 0: the corrective loop runs inside the
deployed agent and its counter is not surfaced on the wire.

Facilitator sessions: one AE session per review session, mapped without
persistence by ``user_id = <review session_id>`` (list-or-create on each
turn). Reconciliation (D25 option B): after an ambiguous stream failure,
the client reads the AE session events and reuses the recorded reply for
its own turn (``recovered_turn_reply``) before re-invoking the model —
at-most-once facilitator execution. Reviewer/synthesis invocations are
single-shot at-least-once retries (a duplicate only costs money, never
conversation state).
"""

from __future__ import annotations

import asyncio
import re
import hashlib
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError
from review_schemas.errors import ErrorBody
from review_schemas.facilitator import FacilitatorTurnOutput
from review_schemas.review import ReviewReport
from review_schemas.synthesis import SynthesisReport

from .ae_messages import (
    render_facilitator_message,
    render_reviewer_message,
    render_synthesis_message,
)
from .agent_clients import (
    AgentCallFailure,
    AgentSet,
    AgentTransportError,
    DeadlineExceeded,
    FacilitatorInvocation,
    FacilitatorResult,
    ReviewerInvocation,
    ReviewerResult,
    SynthesisInvocation,
    SynthesisResult,
    _HttpAgentClient,
)
from .config import Settings

#: Marker the facilitator turn renderer puts in the user message; the
#: reconciliation matcher keys on it (turn numbers are unique per session
#: and the turn lease serializes writers, so the last own-turn message
#: identifies the invocation in doubt).
_TURN_MARKER = "This is turn "


async def _bearer_token() -> str:
    """ADC access token (Cloud Run runtime SA or local user creds)."""
    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _endpoint(resource: str, suffix: str = "") -> str:
    """REST endpoint for one engine resource; region parsed from it.
    Raises ValueError on a malformed resource name (misconfiguration
    surfaced at startup rather than as an IndexError mid-request)."""
    if "/locations/" not in resource:
        raise ValueError(
            f"malformed Agent Engine resource name (no /locations/): {resource!r}"
        )
    region = resource.split("/locations/")[1].split("/")[0]
    return f"https://{region}-aiplatform.googleapis.com/v1/{resource}{suffix}"


def parse_stream_documents(text: str) -> list[dict]:
    """Split the streamQuery response (concatenated JSON documents,
    blank-line separated) into event dicts; a document that is not a JSON
    object is skipped (heartbeat/metadata noise)."""
    events: list[dict] = []
    for chunk in text.split("\n"):
        chunk = chunk.strip()
        if chunk.startswith("data:"):  # tolerate SSE-framed responses
            chunk = chunk[5:].strip()
        if not chunk:
            continue
        try:
            document = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(document, dict):
            events.append(document)
    return events


def _event_texts(event: dict) -> list[str]:
    """Text parts of one event's content, in order."""
    parts = (event.get("content") or {}).get("parts") or []
    return [
        part["text"] for part in parts if isinstance(part, dict) and part.get("text")
    ]


def final_model_reply(events: list[dict]) -> str:
    """The last model-authored text in the stream (the typed final reply).
    User-authored events are skipped; events without text are ignored."""
    reply = ""
    for event in events:
        if event.get("author") == "user":
            continue
        for text in _event_texts(event):
            reply = text
    return reply


def recovered_turn_reply(events: list[dict], turn_number: int) -> str | None:
    """The recorded model reply for our turn, from the session's event
    history (D25 option B matcher).

    Rule: the last user message whose text contains the turn marker
    ``"This is turn <n>"`` (followed by a non-digit, so turn 1 never
    matches turn 10) must be ours; the recovery value is the last
    model-authored text after it. None when our user message is missing
    (the invocation never started), or no reply follows it yet, or a later
    foreign user message exists (cannot attribute the reply)."""
    marker = re.compile(rf"{re.escape(_TURN_MARKER)}{turn_number}(?!\d)")

    def is_own(event: dict) -> bool:
        return any(
            marker.search(text) for text in _event_texts(event)
        )

    last_own_index: int | None = None
    later_user = False
    for index, event in enumerate(events):
        if event.get("author") != "user":
            continue
        if is_own(event):
            last_own_index = index
            later_user = False
        elif last_own_index is not None:
            later_user = True
    if last_own_index is None or later_user:
        return None
    reply = final_model_reply(events[last_own_index + 1 :])
    return reply or None


async def _ae_stream_post(
    url: str, json_body: dict, timeout_s: float
) -> tuple[int, dict]:
    """One real streamQuery round trip: bearer-authenticated POST, the
    concatenated response parsed into events."""
    token = await asyncio.to_thread(_bearer_token)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(
            url, json=json_body, headers={"Authorization": f"Bearer {token}"}
        )
    if response.status_code != 200:
        return response.status_code, _error_from_google(response)
    return 200, {"events": parse_stream_documents(response.text)}


def _error_from_google(response: httpx.Response) -> dict:
    """Google API error body → adapter-shaped error envelope so the shared
    retry machinery (`_HttpAgentClient._error_body`) classifies it: the
    google.rpc `status` block carries code/message/retryability."""
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    return {
        "error": {
            "code": "UPSTREAM_UNAVAILABLE",
            "message": error.get("message") or f"AE returned HTTP {response.status_code}",
            "agent": "agent-engine",
            "correlation_id": str(uuid.uuid4()),
            "retryable": response.status_code >= 500 or response.status_code == 429,
            "retry_after_seconds": 5,
        }
    }


async def _ae_get(url: str, timeout_s: float) -> tuple[int, dict]:
    """One bearer-authenticated GET (session list / event list)."""
    token = await asyncio.to_thread(_bearer_token)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.get(
            url, headers={"Authorization": f"Bearer {token}"}
        )
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body


ListSessions = Callable[[str, str], Awaitable[list[dict]]]
CreateSession = Callable[[str, str], Awaitable[dict]]
ListEvents = Callable[[str, str], Awaitable[list[dict]]]


async def _real_list_sessions(resource: str, user_id: str) -> list[dict]:
    """The AE sessions of one review session (user_id mapping, D25)."""
    status, body = await _ae_get(
        _endpoint(resource, f"/sessions?userId={user_id}"), 10.0
    )
    if status != 200:
        return []
    sessions = body.get("sessions") or body.get("reasoningEnginesSessions") or []
    return [s for s in sessions if s.get("userId", user_id) == user_id]


async def _real_create_session(resource: str, user_id: str) -> dict:
    """Create the AE session for one review session."""
    token = await asyncio.to_thread(_bearer_token)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _endpoint(resource, "/sessions"),
            json={"userId": user_id},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code not in (200, 201):
        raise AgentTransportError(f"AE createSession HTTP {response.status_code}")
    body = response.json()
    body.setdefault("id", body.get("name", "").rsplit("/", 1)[-1])
    return body


async def _real_list_events(resource: str, session_id: str) -> list[dict]:
    """The event history of one AE session (reconciliation reads)."""
    status, body = await _ae_get(
        _endpoint(resource, f"/sessions/{session_id}/events"), 10.0
    )
    if status != 200:
        return []
    return [
        e for e in (body.get("events") or body.get("sessionEvents") or [])
        if isinstance(e, dict)
    ]


def _fingerprint(message: str) -> str:
    """AE-mode prompt_sha256: SHA-256 of the rendered user message."""
    return hashlib.sha256(message.encode()).hexdigest()


def _validated_reply(model, text: str):
    """Parse the final reply with the strict shared schema; an invalid
    reply is a terminal (non-retryable) VALIDATION_ERROR — same semantics
    as the adapters' exhausted corrective loop."""
    try:
        return model.model_validate_json(text)
    except ValidationError as exc:
        raise AgentCallFailure(
            ErrorBody(
                code="VALIDATION_ERROR",
                message=f"AE reply failed schema validation: {exc.error_count()} error(s)",
                correlation_id=uuid.uuid4(),
                retryable=False,
            )
        ) from exc


class AeReviewerClient(_HttpAgentClient):
    """Reviewer invocation over `:streamQuery?alt=sse`."""

    def __init__(self, resource: str, version: str, settings: Settings, **kwargs):
        super().__init__(_endpoint(resource, ":streamQuery?alt=sse"), settings, **kwargs)
        self._resource = resource
        self._version = version

    async def invoke(
        self, request: ReviewerInvocation, *, deadline: float | None = None
    ) -> ReviewerResult:
        deadline_at = deadline or (
            time.monotonic() + self._settings.request_deadline_seconds
        )
        message = render_reviewer_message(request)
        body, attempts = await self._stream(message, deadline_at)
        report = _validated_reply(ReviewReport, body)
        return ReviewerResult(
            report=report,
            agent_version=self._version,
            prompt_sha256=_fingerprint(message),
            transport_attempts=attempts,
        )

    async def _stream(self, message: str, deadline_at: float) -> tuple[Any, int]:
        """The streamQuery attempt chain: retries transport failures and
        retryable (5xx/429) error envelopes per the shared policy; a 200
        without a final model reply is a failed attempt (retryable); a
        non-retryable envelope is terminal. The invocation user_id is
        per-call (stateless reviewers must not share one growing AE
        conversation)."""
        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            timeout_s = self._clamped_timeout(deadline_at)
            try:
                status, body = await self._post(
                    self._url,
                    {
                        "classMethod": "async_stream_query",
                        "input": {
                            "user_id": f"orch-{uuid.uuid4().hex}",
                            "message": message,
                        },
                    },
                    timeout_s,
                )
            except DeadlineExceeded:
                raise
            except Exception as exc:  # transport / timeout
                last_error = exc
            else:
                if status == 200:
                    reply = final_model_reply(body["events"])
                    if reply.strip():
                        return reply, attempt
                    last_error = AgentTransportError(
                        "AE stream ended without a reply"
                    )
                else:
                    error = self._error_body(status, body)
                    if not error.retryable:
                        raise AgentCallFailure(error)
                    last_error = AgentCallFailure(error)
            if attempt < self._attempts:
                await self._backoff(attempt, deadline_at)
        # exhausted: a retryable envelope keeps its structured form (same
        # semantics as the shared HTTP loop); anything else is transport
        if isinstance(last_error, AgentCallFailure):
            raise last_error
        raise AgentTransportError(str(last_error))


class AeSynthesisClient(AeReviewerClient):
    """Synthesis invocation over `:streamQuery?alt=sse`."""

    async def invoke(
        self, request: SynthesisInvocation, *, deadline: float | None = None
    ) -> SynthesisResult:
        deadline_at = deadline or (
            time.monotonic() + self._settings.request_deadline_seconds
        )
        message = render_synthesis_message(request)
        text, attempts = await self._stream(message, deadline_at)
        return SynthesisResult(
            report=_validated_reply(SynthesisReport, text),
            agent_version=self._version,
            prompt_sha256=_fingerprint(message),
            transport_attempts=attempts,
        )


class AeFacilitatorClient(_HttpAgentClient):
    """Facilitator turn over `:streamQuery?alt=sse` with an AE session per
    review session and event-history reconciliation (D25 option B)."""

    def __init__(
        self,
        resource: str,
        version: str,
        settings: Settings,
        *,
        list_sessions: ListSessions = _real_list_sessions,
        create_session: CreateSession = _real_create_session,
        list_events: ListEvents = _real_list_events,
        **kwargs,
    ):
        super().__init__(
            _endpoint(resource, ":streamQuery?alt=sse"),
            settings,
            kind="facilitator",
            **kwargs,
        )
        self._resource = resource
        self._version = version
        self._list_sessions = list_sessions
        self._create_session = create_session
        self._list_events = list_events

    async def _resolve_session(self, session_id: str) -> str:
        """The AE session id for one review session (list-or-create).

        Race note: two concurrent first turns could create two AE sessions
        for one review session (or list eventual-consistency may hide a
        just-created one); the turn lease serializes facilitator turns per
        session, so in practice only the lease-expiry edge can hit this —
        an extra session is a split history, never corruption."""
        sessions = await self._list_sessions(self._resource, session_id)
        if sessions:
            return str(sessions[0].get("id") or sessions[0].get("name", "").rsplit("/", 1)[-1])
        created = await self._create_session(self._resource, session_id)
        return str(created.get("id") or created.get("name", "").rsplit("/", 1)[-1])

    async def _recover(self, request: FacilitatorInvocation) -> dict | None:
        """Read the AE session events and reuse the recorded reply for our
        turn when the ambiguous attempt actually completed (best effort —
        any read failure just lets the retry policy proceed)."""
        try:
            session = await self._resolve_session(request.session_id)
            events = await self._list_events(self._resource, session)
            reply = recovered_turn_reply(events, request.turn_number)
            if reply is None:
                return None
            output = FacilitatorTurnOutput.model_validate_json(reply)
        except Exception:
            return None
        message = render_facilitator_message(request)
        return {
            "output": json.loads(output.model_dump_json()),
            "agent_version": self._version,
            "prompt_sha256": _fingerprint(message),
            "corrective_reprompts": 0,
        }

    async def invoke(
        self, request: FacilitatorInvocation, *, deadline: float | None = None
    ) -> FacilitatorResult:
        deadline_at = deadline or (
            time.monotonic() + self._settings.request_deadline_seconds
        )
        ae_session = await self._resolve_session(request.session_id)
        message = render_facilitator_message(request)
        body: dict | None = None
        last_error: Exception | None = None
        attempts = 0
        for attempt in range(1, self._attempts + 1):
            attempts = attempt
            try:
                timeout_s = self._clamped_timeout(deadline_at)
                status, body = await self._post(
                    self._url,
                    {
                        "classMethod": "async_stream_query",
                        "input": {
                            "user_id": request.session_id,
                            "message": message,
                            "session_id": ae_session,
                        },
                    },
                    timeout_s,
                )
            except DeadlineExceeded:
                raise
            except Exception as exc:  # transport / timeout
                last_error = exc
                body = None
            else:
                if status == 200:
                    reply = final_model_reply(body["events"])
                    if reply.strip():
                        body = {
                            "output": json.loads(reply),
                            "agent_version": self._version,
                            "prompt_sha256": _fingerprint(message),
                            "corrective_reprompts": 0,
                        }
                        break
                    last_error = AgentTransportError(
                        "AE stream ended without a reply"
                    )
                else:
                    error = self._error_body(status, body)
                    if not error.retryable:
                        raise AgentCallFailure(error)
                    last_error = AgentCallFailure(error)
                body = None
            # ambiguous outcome — reconcile against the AE session store
            # before deciding to retry (D25 option B)
            recovered = await self._recover(request)
            if recovered is not None:
                body = recovered
                break
            if attempt < self._attempts:
                await self._backoff(attempt, deadline_at)
        if body is None:
            if isinstance(last_error, AgentCallFailure):
                raise last_error
            raise AgentTransportError(str(last_error))
        output = _validated_reply(FacilitatorTurnOutput, json.dumps(body["output"]))
        return FacilitatorResult(
            output=output,
            agent_version=body.get("agent_version", self._version),
            prompt_sha256=body.get("prompt_sha256", _fingerprint(message)),
            corrective_reprompts=body.get("corrective_reprompts", 0),
            transport_attempts=attempts,
        )


def ae_agent_set(settings: Settings) -> AgentSet:
    """The four AE clients (live tier; D25)."""
    kwargs: dict[str, Any] = {"post": _ae_stream_post}
    return AgentSet(
        business=AeReviewerClient(
            settings.ae_business_resource, settings.ae_business_version,
            settings, **kwargs,
        ),
        engineering=AeReviewerClient(
            settings.ae_engineering_resource, settings.ae_engineering_version,
            settings, **kwargs,
        ),
        synthesis=AeSynthesisClient(
            settings.ae_synthesis_resource, settings.ae_synthesis_version,
            settings, **kwargs,
        ),
        facilitator=AeFacilitatorClient(
            settings.ae_facilitator_resource, settings.ae_facilitator_version,
            settings, **kwargs,
        ),
    )
