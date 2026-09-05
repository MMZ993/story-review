"""Verified-caller principal for the connectivity-spike MCP service.

The deployed service resolves the principal from a verified Google ID token
(audience = the Cloud Run service URL). Tests inject a fake verified principal
through the same interface instead of disabling the authorization boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """A verified caller identity.

    Attributes:
        email: The caller's identity (service-account email in production).
        subject: Optional unique subject of the verified token.
    """

    email: str
    subject: str | None = None
