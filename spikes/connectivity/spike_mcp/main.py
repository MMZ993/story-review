"""Container entrypoint for the connectivity-spike MCP service.

uvicorn target: `uvicorn spike_mcp.main:application --host 0.0.0.0 --port 8080`.
Configuration comes from environment variables set by Terraform (see
`spike_mcp/app.py`).
"""

from spike_mcp.app import build_app

application = build_app()
