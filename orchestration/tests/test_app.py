"""Config loading tests (health/stories coverage lives in
 test_stories_api.py / test_stack_stories.py from increment 1)."""

from __future__ import annotations

import pytest


def test_settings_require_mandatory_env(monkeypatch):
    for name in (
        "ORCH_DB_DSN",
        "ORCH_STORY_URL",
        "ORCH_ARTIFACT_URL",
        "ORCH_REPORT_URL",
        "ORCH_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)
    from orchestration.config import Settings

    with pytest.raises(ValueError):
        Settings.from_env()


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("ORCH_DB_DSN", "postgresql://x")
    monkeypatch.setenv("ORCH_STORY_URL", "http://story:8080/mcp")
    monkeypatch.setenv("ORCH_ARTIFACT_URL", "http://artifact:8080/mcp")
    monkeypatch.setenv("ORCH_REPORT_URL", "http://report:8080/mcp")
    monkeypatch.setenv("ORCH_BUCKET", "artifacts-local")
    import orchestration.config as config

    settings = config.Settings.from_env()
    assert settings.story_url == "http://story:8080/mcp"
    assert settings.request_deadline_seconds == 300
    assert settings.short_call_timeout_seconds == 60
    assert settings.facilitator_timeout_seconds == 120
