"""Strict environment-driven configuration for the webui service.

The webui is a static shell plus a thin same-origin reverse proxy: the only
operational input is the orchestration base URL (the proxy target). No
database, no downstream clients of its own.

Errors: ValueError from from_env() naming the missing mandatory variable —
the service fails fast at startup (D17-1 + amendment).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_MANDATORY = ("ORCHESTRATION_BASE_URL",)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration; constructed only via from_env()."""

    orchestration_base_url: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        """Build Settings from the environment (or an explicit mapping).

        Raises ValueError naming the first missing mandatory variable.
        """
        source = dict(os.environ) if env is None else env
        values = {}
        for name in _MANDATORY:
            values[name] = source.get(name, "").strip().rstrip("/")
            if not values[name]:
                raise ValueError(f"missing mandatory environment variable: {name}")
        return cls(orchestration_base_url=values["ORCHESTRATION_BASE_URL"])
