"""Health endpoint with downstream reachability flags (api-contract.md).

Liveness only: one probe attempt per configured MCP downstream (story,
artifact, report). Never raises — an unreachable downstream degrades status.
The database flag is added in increment 2, when the app owns an asyncpg pool.
"""

from __future__ import annotations

from dataclasses import dataclass

from review_schemas.api import HealthDependency, HealthResponse


@dataclass(frozen=True)
class Downstream:
    name: str
    client: object  # McpClient duck-typed (probe())


async def dependencies_state(downstreams: list[Downstream]) -> HealthResponse:
    """Probe every downstream concurrently; ok iff all reachable."""
    import asyncio

    reachable = await asyncio.gather(
        *(d.client.probe() for d in downstreams)
    )
    dependencies = [
        HealthDependency(name=d.name, reachable=bool(ok))
        for d, ok in zip(downstreams, reachable, strict=True)
    ]
    status = "ok" if all(dep.reachable for dep in dependencies) else "degraded"
    return HealthResponse(status=status, dependencies=dependencies)
