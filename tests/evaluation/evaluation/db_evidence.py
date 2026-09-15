"""Read-only Postgres evidence queries (evaluation increment 1).

Two read paths over the compose postgres (host port, local-agents
profile only):

- ``agent_runs`` rows for a session from the ``orchestration`` database
  (fan-out/audit assertions);
- the facilitator ADK session-event trace from the ``facilitator``
  database (function_call events = agent-initiated MCP tool calls).

The ADK events table is discovered at runtime (name/columns vary across
ADK versions); only SELECTs are issued.
"""

from __future__ import annotations

import asyncio
import json

import asyncpg

from evaluation.capture import AgentRunEvidence

#: Tool names proving facilitator-driven Story-MCP use (read-only tools).
STORY_MCP_TOOLS = frozenset({"get_story", "list_stories"})


async def _fetch_agent_rows(dsn: str, session_id: str) -> list[AgentRunEvidence]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "select agent, agent_version, prompt_sha256, state, "
            "transport_attempts, corrective_reprompts, started_at, finished_at "
            "from agent_runs where session_id = $1 order by agent_run_id",
            session_id,
        )
        return [AgentRunEvidence.model_validate(dict(row)) for row in rows]
    finally:
        await conn.close()


async def _discover_events_columns(conn: asyncpg.Connection) -> tuple[str, list[str]]:
    """Find the ADK events table and its column names (version-tolerant).

    Exact name ``events`` wins; otherwise the alphabetically first table
    whose name contains ``event`` with ``session_id`` and a payload column
    (``content`` or ``event_data`` — ADK's schema varies by version).
    """
    rows = await conn.fetch(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'public'"
    )
    by_table: dict[str, set[str]] = {}
    for row in rows:
        by_table.setdefault(row["table_name"], set()).add(row["column_name"])
    candidates = [
        table
        for table, columns in by_table.items()
        if "event" in table
        and "session_id" in columns
        and ("content" in columns or "event_data" in columns)
    ]
    if "events" in candidates:
        return "events", sorted(by_table["events"])
    if candidates:
        table = sorted(candidates)[0]
        return table, sorted(by_table[table])
    raise RuntimeError(f"no ADK events table found; tables: {sorted(by_table)}")


def _tool_call_names(content_json: str) -> list[str]:
    """Function-call tool names inside one ADK event content blob.

    Tolerates both shapes: a bare content object (``parts`` at the top
    level) and an ``event_data`` blob whose parts sit under an inner
    ``content`` object.
    """
    try:
        content = json.loads(content_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(content, dict):
        return []
    inner = content.get("content")
    if isinstance(inner, dict):
        content = inner
    names = []
    for part in content.get("parts", []):
        call = part.get("function_call")
        if isinstance(call, dict) and call.get("name"):
            names.append(call["name"])
    return names


def _payload_column(columns: list[str]) -> str:
    """The event payload column present in this table's schema."""
    if "content" in columns:
        return "content"
    return "event_data"


def _rows_to_tool_names(rows, payload: str) -> list[str]:
    """Decode payload cells (str or jsonb dict) into tool-call names."""
    names: list[str] = []
    for row in rows:
        content = row[payload]
        text = content if isinstance(content, str) else json.dumps(content)
        names.extend(_tool_call_names(text))
    return names


async def _fetch_tool_calls(dsn: str, session_id: str) -> list[str]:
    conn = await asyncpg.connect(dsn)
    try:
        table, columns = await _discover_events_columns(conn)
        payload = _payload_column(columns)
        rows = await conn.fetch(
            f"select {payload} from {table} where session_id = $1", session_id
        )
        return _rows_to_tool_names(rows, payload)
    finally:
        await conn.close()


def fetch_agent_runs(dsn: str, session_id: str) -> list[AgentRunEvidence]:
    """Audit rows for one session (orchestration database)."""
    return asyncio.run(_fetch_agent_rows(dsn, session_id))


def fetch_facilitator_tool_calls(dsn: str, session_id: str) -> list[str]:
    """All function-call tool names in the session's ADK event trace."""
    return asyncio.run(_fetch_tool_calls(dsn, session_id))
