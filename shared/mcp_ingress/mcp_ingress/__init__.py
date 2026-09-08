"""Shared ID-token ingress middleware for the MCP servers."""

from mcp_ingress.auth import (
    IdTokenAuthMiddleware,
    Verifier,
    current_principal,
    google_token_verifier,
)

__all__ = [
    "IdTokenAuthMiddleware",
    "Verifier",
    "current_principal",
    "google_token_verifier",
]
