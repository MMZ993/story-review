"""Container entrypoint for the artifact MCP service.

uvicorn target: `uvicorn artifact_mcp.main:application --host 0.0.0.0 --port 8080`.
Configuration comes from environment variables (see `artifact_mcp/app.py`).
"""

from artifact_mcp.app import build_app

application = build_app()
