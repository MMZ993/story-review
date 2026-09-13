"""Audience-scoped ID-token bearer headers for MCP service calls.

On Cloud Run the MCP services sit behind two verifiers that both key on
an ID token whose audience is the target service's URL: the Cloud Run
ingress IAM check and the mcp_ingress middleware (docs/operations/
connectivity-identity.md — the runtime SA email is the token's issuer
identity, not the audience). The token is minted from the attached
service account via the metadata server; sa-orchestration holds
`iam.serviceAccountTokenCreator` on itself for exactly this.

Tokens are cached per audience until shortly before their ~1 h expiry —
metadata minting per call would add avoidable latency to every MCP
round trip. No metadata server exists locally (compose/deterministic
tier): callers keep MCP auth off there and never reach this module.
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request

#: Refresh a cached token this many seconds before its stated expiry.
_EXPIRY_MARGIN_SECONDS = 60.0

#: Bearer header value for a raw token.
_bearer = "Bearer {}"

_cache: dict[str, tuple[str, float]] = {}


def metadata_id_token(
    audience: str, _fetch=None, _now=time.monotonic
) -> dict[str, str]:
    """Authorization headers with an audience-scoped ID token.

    ``_fetch``/``_now`` are injectable seams for deterministic tests.
    Raises OSError if the metadata server is unreachable (local runs keep
    MCP auth disabled instead — see config.mcp_id_token_auth).
    """
    cached = _cache.get(audience)
    if cached and cached[1] > _now() + _EXPIRY_MARGIN_SECONDS:
        return {"Authorization": _bearer.format(cached[0])}

    token, expires_at = _mint(audience, _fetch, _now)
    _cache[audience] = (token, expires_at)
    return {"Authorization": _bearer.format(token)}


def _mint(
    audience: str, _fetch=None, _now=time.monotonic
) -> tuple[str, float]:
    """One metadata-server mint returning (token, monotonic expiry)."""
    if _fetch is None:
        def _fetch(url: str) -> tuple[str, str]:
            req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode()
                expires = response.headers.get("X-Metadata-Token-Expires-In-Seconds")
                return body, expires or "3600"

    url = (
        "http://metadata.google.internal/computeMetadata/v1/"
        "instance/service-accounts/default/identity?audience="
        + urllib.parse.quote(audience, safe="")
        + "&format=full"
    )
    token, expires_in = _fetch(url)
    return token.strip(), _now() + float(expires_in)
