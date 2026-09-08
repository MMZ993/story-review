"""Container entrypoint for the story MCP service.

uvicorn target: `uvicorn story_mcp.main:application --host 0.0.0.0 --port 8080`.
Configuration comes from environment variables (see `story_mcp/app.py`).
"""

from story_mcp.app import build_app

application = build_app()
