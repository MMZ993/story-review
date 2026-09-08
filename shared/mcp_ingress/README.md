# mcp-ingress

Shared ID-token ingress middleware and caller-principal contextvar for the
three Phase-4 MCP servers (story, artifact, report). Extracted at increment 3
when the third copy of the story/artifact `auth.py` would otherwise have been
written (diff-verified identical modulo logger/contextvar names).

The package is pure ASGI (no Starlette/FastAPI dependency) and reads no
environment: each server's `app.py` owns its env names (`STORY_*`,
`ARTIFACT_*`, `REPORT_*`) and only the fail-closed wiring rules live here.

Run tests: `make mcp-ingress-test`.
