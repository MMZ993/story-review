"""Stateless judge client (Phase 9 increment 0).

One plain Vertex AI call per case (temperature 0, one candidate, via
google-genai ADC like the agents themselves). Fixed retry/fail policy per
docs/quality/evaluation-tests.md: exactly one retry with identical input
on a transient transport failure; a second transport failure or invalid
structured output fails the case; no best-of-N, no resampling, no score
selection — ever.

The transport is injectable for unit tests: anything callable
``(contents: str) -> JudgeTransportReply``. The live transport is built by
``live_transport`` and lazily imports google-genai.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Protocol

from evaluation.models import JudgeResult

MAX_ATTEMPTS = 2  # one original call + one identical retry, per policy


class JudgeTransportError(Exception):
    """A transient transport failure (network error, 5xx) — retryable once."""


class JudgeFailure(Exception):
    """The case failed the judge stage: not retryable."""


@dataclass(frozen=True)
class JudgeTransportReply:
    """Raw model reply text plus the publisher model/version metadata."""

    text: str
    publisher_model: str


class Transport(Protocol):
    def __call__(self, contents: str) -> JudgeTransportReply: ...


class JudgeCaseFn(Protocol):
    """The judge-call entry point (injectable for the judge stage)."""

    def __call__(
        self,
        *,
        case_id: str,
        prompt_text: str,
        case_input: dict,
        transport: Transport,
        judge_model: str,
    ) -> "JudgeCallOutcome": ...


@dataclass(frozen=True)
class JudgeCallOutcome:
    """A successful judge call: typed verdict + recorded metadata."""

    result: JudgeResult
    publisher_model: str
    attempts: int


def render_judge_message(prompt_text: str, case_input: dict) -> str:
    """Assemble the single judge message: prompt + case input as JSON."""
    return (
        f"{prompt_text}\n\n---\n\n"
        f"CASE INPUT (JSON):\n{json.dumps(case_input, ensure_ascii=False, indent=2)}"
    )


def judge_case(
    *,
    case_id: str,
    prompt_text: str,
    case_input: dict,
    transport: Transport,
    judge_model: str,
) -> JudgeCallOutcome:
    """Run one judge call under the fixed policy.

    Returns the typed outcome on success. Raises JudgeFailure when the
    structured output is invalid (no retry) or a second transport failure
    occurs. Never samples more than twice, never selects among samples.
    """
    contents = render_judge_message(prompt_text, case_input)
    last_transport_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            reply = transport(contents)
        except JudgeTransportError as exc:
            last_transport_error = exc
            continue
        try:
            payload = json.loads(reply.text)
        except ValueError as exc:
            raise JudgeFailure(
                f"case {case_id}: judge structured output is not JSON: {exc}"
            ) from exc
        try:
            result = JudgeResult.model_validate(payload)
        except Exception as exc:
            raise JudgeFailure(
                f"case {case_id}: judge structured output invalid: {exc}"
            ) from exc
        return JudgeCallOutcome(
            result=result, publisher_model=reply.publisher_model, attempts=attempt
        )

    raise JudgeFailure(
        f"case {case_id}: judge transport failure after "
        f"{MAX_ATTEMPTS} attempts: {last_transport_error}"
    )


def live_transport(model: str, location: str, temperature: float) -> Transport:
    """Build the real Vertex AI transport (google-genai, ADC).

    Network errors and 5xx API errors raise JudgeTransportError (retryable
    once by judge_case); 4xx API errors are non-retryable — surfaced as
    JudgeFailure directly, since retrying an identical rejected request
    cannot help.
    """
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types

    client = genai.Client(vertexai=True, location=location)

    def _transport(contents: str) -> JudgeTransportReply:
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    candidate_count=1,
                    response_mime_type="application/json",
                ),
            )
        except genai_errors.APIConnectionError as exc:
            raise JudgeTransportError(f"connection failure: {exc}") from exc
        except genai_errors.ClientError as exc:
            raise JudgeFailure(f"judge call rejected (4xx): {exc}") from exc
        except genai_errors.ServerError as exc:
            raise JudgeTransportError(f"server error (5xx): {exc}") from exc
        publisher = getattr(response, "model_version", None) or model
        text = response.text
        if not text:
            raise JudgeTransportError("judge returned no text (empty response)")
        return JudgeTransportReply(text=text, publisher_model=str(publisher))

    return _transport
