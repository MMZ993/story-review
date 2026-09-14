"""Keyless IAM-backed Signing credentials for live V4 signed URLs.

Cloud Run ambient credentials are metadata-token credentials — they carry
no private key, so the storage library's client-side V4 signing
(``ensure_signed_credentials``) rejects them with AttributeError. The
keyless alternative (no SA key files, per AGENTS.md): sign via the IAM
``signBlob`` API as the attached service account, which holds
``roles/iam.serviceAccountTokenCreator`` on itself (infra/main.tf).

The Signing seam is deliberately minimal: ``sign_bytes`` + ``signer_email``
are all the storage library's V4 path needs. HTTP access is behind an
injectable transport; the access token behind an injectable getter — the
deterministic tests pass plain callables, the runtime wiring uses ADC.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Callable

from google.auth.credentials import Credentials, Signing

#: (url, token, payload) -> response body bytes
Transport = Callable[..., bytes]
#: () -> access token string
TokenGetter = Callable[[], str]

_IAM_BASE = "https://iamcredentials.googleapis.com/v1"


def iam_signer_email(adc_credentials: Any, *, hint: str = "") -> str:
    """Resolve the signing principal: explicit env override wins, then
    the configured hint, then the attached credentials' service-account
    email; raise if none is available."""
    override = os.environ.get("ORCH_SIGNER_EMAIL", "").strip()
    if override:
        return override
    email = (hint or "").strip() or getattr(
        adc_credentials, "service_account_email", ""
    ) or ""
    if email:
        return email
    raise RuntimeError(
        "cannot determine the IAM signing service account: set "
        "ORCH_SIGNER_EMAIL or run with attached service-account credentials"
    )


def _default_transport() -> Transport:
    def transport(url: str, *, token: str, payload: dict) -> bytes:
        import urllib.request

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()

    return transport


def _default_token_getter() -> TokenGetter:
    def getter() -> str:
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token

    return getter


class IamSignBlobCredentials(Credentials, Signing):
    """A ``Signing`` credential whose private key lives in IAM.

    ``refresh`` is a no-op: these credentials never authenticate a
    request themselves — the storage library only reads
    ``sign_bytes``/``signer_email`` from them.
    """

    def __init__(
        self,
        signer_email: str,
        *,
        transport: Transport | None = None,
        token: str | None = None,
        token_getter: TokenGetter | None = None,
    ) -> None:
        self._email = signer_email
        self._transport = transport or _default_transport()
        if token is not None:
            self._token_getter: TokenGetter = lambda: token
        else:
            self._token_getter = token_getter or _default_token_getter()

    @property
    def signer_email(self) -> str:
        return self._email

    @property
    def signer(self) -> None:  # noqa: ARG002 — Signing seam; unused by V4
        """No local signer exists — signatures come from IAM."""
        return None

    def refresh(self, request: Any) -> None:  # noqa: ARG002 — Credentials API
        return None

    def sign_bytes(self, message: bytes) -> bytes:
        """One IAM signBlob call; returns the raw signature bytes."""
        url = f"{_IAM_BASE}/projects/-/serviceAccounts/{self._email}:signBlob"
        body = {
            "payload": base64.urlsafe_b64encode(message).decode().rstrip("=")
        }
        response = self._transport(url, token=self._token_getter(), payload=body)
        signed = json.loads(response.decode())["signedBlob"]
        return base64.b64decode(signed)
