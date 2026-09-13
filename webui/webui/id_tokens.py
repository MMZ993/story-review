"""Audience-scoped ID-token bearer header for the orchestration proxy hop.

On Cloud Run the orchestration service is IAM-gated (no unauthenticated
ingress, connectivity-identity.md): the webui's /api proxy must present an
ID token whose audience is the orchestration service URL, minted from the
attached service account via the metadata server (sa-webui holds
roles/run.invoker on orchestration). This mirrors orchestration's
id_tokens.py, reduced to the single audience the webui needs.

Tokens are cached until shortly before expiry — metadata minting per call
would add avoidable latency to every proxied request. No metadata server
exists locally (compose/deterministic tier): the flag stays off there and
this module is never reached.
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request

#: Refresh a cached token this many seconds before its stated expiry.
_EXPIRY_MARGIN_SECONDS = 60.0

_bearer = "Bearer {}"

_cache: tuple[str, float] | None = None


def metadata_id_token(
    audience: str, _fetch=None, _now=time.monotonic
) -> dict[str, str]:
    """Authorization headers with an audience-scoped ID token.

    ``_fetch``/``_now`` are injectable seams for deterministic tests.
    Raises OSError if the metadata server is unreachable or mints an
    empty token (local runs keep proxy auth disabled instead — see
    config.orchestration_id_token_auth).
    """
    global _cache
    if _cache and _cache[1] > _now() + _EXPIRY_MARGIN_SECONDS:
        return {"Authorization": _bearer.format(_cache[0])}

    token, expires_at = _mint(audience, _fetch, _now)
    _cache = (token, expires_at)
    return {"Authorization": _bearer.format(token)}


def _mint(audience: str, _fetch=None, _now=time.monotonic) -> tuple[str, float]:
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
    if not token.strip():
        # Observed on Cloud Run: 200 with an empty body. Fail loud (and
        # observably) instead of sending "Bearer " to the ingress.
        import logging

        logging.getLogger(__name__).error(
            "metadata identity endpoint returned an empty token for "
            "audience %s (url: %s)", audience, url,
        )
        raise OSError("metadata identity endpoint returned an empty token")
    return token.strip(), _now() + float(expires_in)
