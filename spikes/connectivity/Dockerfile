# Connectivity spike MCP service image (Phase 1, disposable).
# Build context: spikes/connectivity (see deploy-mcp.sh).
FROM python:3.13-slim

COPY spike_mcp/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

COPY spike_mcp/ /app/spike_mcp/
ENV PYTHONPATH=/app

# Run as non-root.
USER nobody

CMD ["python", "-m", "uvicorn", "spike_mcp.main:application", "--host", "0.0.0.0", "--port", "8080"]
