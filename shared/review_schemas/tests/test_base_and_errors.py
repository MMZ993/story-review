"""Tests for the strict primitives in review_schemas.base.

Covers the observable contract from docs/design/schemas.md "Strict base types":
unknown-field rejection, strict-mode rejection of coerced values (Python mode),
JSON-mode string decoding of UUIDs and timestamps, identifier patterns, text
bounds and whitespace stripping, and timezone-aware datetimes.

The ErrorBody/ErrorEnvelope/ToolError tests (same specification section file)
are added with increment 2.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_schemas.base import (
    ArtifactId,
    AgentRunId,
    Format,
    HttpsUrl,
    IdempotencyKey,
    RunId,
    SessionId,
    Sha256,
    ShortText,
    StoryId,
    Text,
    UtcDatetime,
    StrictModel,
)

from conftest import FIXED_TS, FIXED_TS_JSON, FIXED_UUID, UUID_STR


class _Probe(StrictModel):
    """Minimal model exposing one field of each primitive under test."""

    story_id: StoryId
    run_id: RunId
    session_id: SessionId
    artifact_id: ArtifactId
    agent_run_id: AgentRunId
    text: Text
    short_text: ShortText
    sha256: Sha256
    url: HttpsUrl
    when: UtcDatetime
    key: IdempotencyKey
    fmt: Format


def valid_payload() -> dict:
    """One fully valid Python-mode payload (the happy path for rejection tests)."""
    return {
        "story_id": "story-01",
        "run_id": f"run-{UUID_STR}",
        "session_id": f"sess-{UUID_STR}",
        "artifact_id": f"art-{UUID_STR}",
        "agent_run_id": f"arun-{UUID_STR}",
        "text": "some body text",
        "short_text": "summary",
        "sha256": "ab" * 32,
        "url": "https://example.com/x",
        "when": FIXED_TS,
        "key": FIXED_UUID,
        "fmt": "md",
    }


class TestUnknownFieldRejection:
    def test_extra_field_rejected(self):
        payload = valid_payload() | {"surprise": 1}
        with pytest.raises(ValidationError, match="surprise"):
            _Probe.model_validate(payload)

    def test_json_mode_extra_field_rejected(self):
        import json

        payload = valid_payload()
        payload["key"] = str(FIXED_UUID)
        payload["when"] = FIXED_TS_JSON
        payload["surprise"] = 1
        with pytest.raises(ValidationError, match="surprise"):
            _Probe.model_validate_json(json.dumps(payload))


class TestStrictModeRejections:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("key", str(FIXED_UUID)),  # UUID string must NOT coerce in Python mode
            ("when", FIXED_TS_JSON),  # timestamp string must NOT coerce
            ("key", 12345),
        ],
    )
    def test_python_mode_coercion_rejected(self, field, value):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {field: value})


class TestJsonModeDecoding:
    def test_json_mode_accepts_uuid_and_timestamp_strings(self):
        import json

        payload = valid_payload()
        payload["key"] = str(FIXED_UUID)
        payload["when"] = FIXED_TS_JSON
        model = _Probe.model_validate_json(json.dumps(payload))
        assert model.key == FIXED_UUID
        assert model.when == FIXED_TS

    def test_json_mode_rejects_malformed_uuid(self):
        import json

        payload = valid_payload()
        payload["key"] = str(FIXED_UUID)
        payload["when"] = FIXED_TS_JSON
        payload["key"] = str(FIXED_UUID)[:-1]
        with pytest.raises(ValidationError):
            _Probe.model_validate_json(json.dumps(payload))


class TestIdentifierPatterns:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("story_id", "story-1"),  # too short
            ("story_id", "story-1a"),  # non-digit
            ("run_id", f"run-{UUID_STR}0"),  # wrong length
            ("run_id", f"run-{(UUID_STR)[:-1]}g"),  # non-hex char
            ("session_id", f"run-{UUID_STR}"),  # wrong prefix
            ("artifact_id", f"sess-{UUID_STR}"),  # wrong prefix
            ("agent_run_id", f"arun-{(UUID_STR)[:-1]}z"),
        ],
    )
    def test_invalid_identifier_rejected(self, field, value):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {field: value})

    def test_all_prefixes_accepted(self):
        assert _Probe.model_validate(valid_payload()).run_id.startswith("run-")


class TestTextBounds:
    def test_text_stripped(self):
        model = _Probe.model_validate(valid_payload() | {"text": "  padded  "})
        assert model.text == "padded"

    def test_empty_after_strip_rejected(self):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"text": "   "})

    def test_text_upper_bound(self):
        ok = _Probe.model_validate(valid_payload() | {"text": "a" * 20_000})
        assert len(ok.text) == 20_000
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"text": "a" * 20_001})

    def test_short_text_upper_bound(self):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"short_text": "a" * 501})
        assert len(_Probe.model_validate(valid_payload() | {"short_text": "a" * 500}).short_text) == 500


class TestSha256AndUrl:
    def test_sha256_requires_64_lowercase_hex(self):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"sha256": "AB" * 32})
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"sha256": "ab" * 31})

    def test_url_must_be_https(self):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"url": "http://example.com"})


class TestUtcDatetime:
    def test_naive_datetime_rejected(self):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"when": FIXED_TS.replace(tzinfo=None)})

    def test_non_utc_timezone_accepted_aware(self):
        from datetime import timedelta, timezone

        other_tz = timezone(timedelta(hours=2))
        model = _Probe.model_validate(valid_payload() | {"when": FIXED_TS.astimezone(other_tz)})
        # Any aware datetime is accepted; UTC normalization is a serialization concern.
        assert model.when.utcoffset() == timedelta(hours=2)


class TestFormatLiteral:
    @pytest.mark.parametrize("value", ["md", "pdf"])
    def test_formats_accepted(self, value):
        assert _Probe.model_validate(valid_payload() | {"fmt": value}).fmt == value

    def test_other_format_rejected(self):
        with pytest.raises(ValidationError):
            _Probe.model_validate(valid_payload() | {"fmt": "docx"})
