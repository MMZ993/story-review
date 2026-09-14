"""IAM signBlob-backed Signing credentials (live signed URLs on Cloud Run).

Cloud Run ambient credentials are metadata-token credentials — they cannot
sign V4 URLs client-side (no private key). The keyless alternative is the
IAM signBlob API as the attached service account, which holds
roles/iam.serviceAccountTokenCreator on itself (infra/main.tf).

Deterministic tier: the HTTP call sits behind an injectable transport; no
network, no metadata server.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Callable

import pytest
from google.cloud import storage

from orchestration.iam_signing import (
    IamSignBlobCredentials,
    iam_signer_email,
)


def _fake_transport(response_body: bytes) -> tuple[Callable, list[dict]]:
    """Return (transport, requests) — records what the signer sent."""
    requests: list[dict] = []

    def transport(url: str, *, token: str, payload: dict) -> bytes:
        requests.append({"url": url, "token": token, "payload": payload})
        return response_body

    return transport, requests


class TestSignBytes:
    def test_signs_via_the_iam_signblob_api(self) -> None:
        signature = base64.b64encode(b"\x01\x02sig").decode()
        transport, requests = _fake_transport(json.dumps({"signedBlob": signature}).encode())

        creds = IamSignBlobCredentials(
            "sa-x@test.iam", transport=transport, token="bearer-token"
        )
        assert creds.sign_bytes(b"hello") == b"\x01\x02sig"

        (call,) = requests
        assert call["url"].endswith(
            "/projects/-/serviceAccounts/sa-x@test.iam:signBlob"
        )
        assert call["payload"] == {
            "payload": base64.urlsafe_b64encode(b"hello").decode().rstrip("=")
        }
        assert call["token"] == "bearer-token"

    def test_is_a_signing_credential_for_the_storage_library(self) -> None:
        signature = base64.b64encode(b"sig").decode()
        ok_transport, _ = _fake_transport(
            json.dumps({"signedBlob": signature}).encode()
        )
        creds = IamSignBlobCredentials(
            "sa-x@test.iam", transport=ok_transport, token="t"
        )
        # the exact gate google.cloud.storage raises on (ensure_signed_credentials)
        assert hasattr(creds, "sign_bytes") and creds.signer_email == "sa-x@test.iam"
        # the full V4 path works offline with these credentials
        bucket = storage.Client(
            project="test", credentials=_anonymous()
        ).bucket("reports")
        url = bucket.blob("runs/r/reports/a.md").generate_signed_url(
            version="v4", expiration=900, credentials=creds
        )
        assert "X-Goog-Credential=sa-x%40test.iam%2F" in url

    def test_signer_email_overrides_from_environment(self, monkeypatch) -> None:
        class _Creds:
            service_account_email = "attached@test.iam"

        monkeypatch.setenv("ORCH_SIGNER_EMAIL", "explicit@test.iam")
        assert iam_signer_email(_Creds()) == "explicit@test.iam"

    def test_signer_email_falls_back_to_attached_credentials(self, monkeypatch) -> None:
        monkeypatch.delenv("ORCH_SIGNER_EMAIL", raising=False)

        class _Creds:
            service_account_email = "attached@test.iam"

        assert iam_signer_email(_Creds()) == "attached@test.iam"


def _anonymous() -> Any:
    from google.auth.credentials import AnonymousCredentials

    return AnonymousCredentials()
