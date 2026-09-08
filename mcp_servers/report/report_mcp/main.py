"""Container entrypoint for the report MCP service.

uvicorn target: `uvicorn report_mcp.main:application --host 0.0.0.0 --port 8080`.
Configuration comes from environment variables (see `report_mcp/app.py`).
"""

from report_mcp.app import build_app

application = build_app()
