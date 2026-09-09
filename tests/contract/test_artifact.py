"""Artifact-server contract over the compose wire (fake GCS): save/get
roundtrip, lineage scoping, and idempotent retries — including one retry
across a container restart, which only the compose stack can prove.
"""

from __future__ import annotations

import subprocess

from conftest import (
    ARTIFACT_URL,
    call_tool,
    error,
    new_key,
    payload,
    run_id,
    checksum,
)


def _story_content() -> dict:
    return {
        "story_id": "story-01",
        "title": "Invoice PDF in the confirmation email",
        "status": "New",
        "description": "Buyers receive the invoice as a PDF attachment.",
        "acceptance_criteria": ["PDF attached", "Email within 5 minutes"],
        "epic_context": "Epic — Feature",
        "roadmap_context": "Roadmap context text.",
        "comments": [],
        "context_stories": [],
    }


def _save_args(run: str, key: str | None = None) -> dict:
    return {
        "type": "story",
        "story_run_id": run,
        "perspective": None,
        "content": _story_content(),
        "idempotency_key": key or new_key(),
    }


def test_save_and_get_roundtrip():
    run = run_id()
    saved = payload(call_tool(ARTIFACT_URL, "save_artifact", _save_args(run)))
    assert saved["created"] is True
    reference = saved["reference"]
    assert reference["story_run_id"] == run

    got = payload(
        call_tool(
            ARTIFACT_URL, "get_artifact", {"story_run_id": run, "artifact_id": reference["artifact_id"]}
        )
    )
    assert got["content"] == _story_content()
    assert got["reference"]["checksum_sha256"] == checksum(_story_content())


def test_retry_same_key_returns_same_reference():
    run = run_id()
    key = new_key()
    first = payload(call_tool(ARTIFACT_URL, "save_artifact", _save_args(run, key)))
    second = payload(call_tool(ARTIFACT_URL, "save_artifact", _save_args(run, key)))
    assert second["created"] is False
    assert second["reference"]["artifact_id"] == first["reference"]["artifact_id"]


def test_same_key_different_content_is_reused_error():
    run = run_id()
    key = new_key()
    call_tool(ARTIFACT_URL, "save_artifact", _save_args(run, key))
    args = _save_args(run, key)
    args["content"]["title"] = "Changed title"
    result = call_tool(ARTIFACT_URL, "save_artifact", args)
    assert error(result)["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert error(result)["retryable"] is False


def test_cross_run_read_is_not_found():
    run = run_id()
    saved = payload(call_tool(ARTIFACT_URL, "save_artifact", _save_args(run)))
    result = call_tool(
        ARTIFACT_URL,
        "get_artifact",
        {"story_run_id": run_id(), "artifact_id": saved["reference"]["artifact_id"]},
    )
    assert error(result)["code"] == "ARTIFACT_NOT_FOUND"


def test_idempotency_survives_container_restart():
    """The durable-idempotency requirement: a retry after the server process
    dies must not create a duplicate — the key lives in (fake) GCS, not memory.
    """
    run = run_id()
    key = new_key()
    first = payload(call_tool(ARTIFACT_URL, "save_artifact", _save_args(run, key)))

    subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "local",
            "--env-file",
            "env/.env",
            "restart",
            "artifact",
        ],
        cwd="../../deploy",
        check=True,
        capture_output=True,
    )

    from conftest import wait_healthy

    wait_healthy(ARTIFACT_URL, timeout_s=60)
    second = payload(call_tool(ARTIFACT_URL, "save_artifact", _save_args(run, key)))
    assert second["created"] is False
    assert second["reference"]["artifact_id"] == first["reference"]["artifact_id"]
