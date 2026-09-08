# Artifact MCP server image (Phase 4 increment 2).
# Build context: repository root —
#   docker build -f mcp_servers/artifact/Dockerfile .
#
# No dataset content is ever involved (guard below); artifacts live in the
# configured bucket (fake-gcs-server endpoint locally, real GCS in Cloud Run).
FROM python:3.13-slim

COPY mcp_servers/artifact/requirements.lock /tmp/artifact-requirements.lock
RUN pip install --no-cache-dir -r /tmp/artifact-requirements.lock

COPY shared/review_schemas/review_schemas /app/shared/review_schemas
COPY mcp_servers/artifact/artifact_mcp /app/artifact_mcp
ENV PYTHONPATH=/app:/app/shared

# Build-time guard: dataset content must never ride along.
RUN ! find /app -path "*dataset/stories*" -o -path "*dataset/expected*" | grep -q .

# Run as non-root.
USER nobody

CMD ["python", "-m", "uvicorn", "artifact_mcp.main:application", "--host", "0.0.0.0", "--port", "8080"]
