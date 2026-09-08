# Report MCP server image (Phase 4 increment 3).
# Build context: repository root —
#   docker build -f mcp_servers/report/Dockerfile .
#
# No dataset content is ever involved (guard below); reports are rendered
# from finalized-review artifacts in the shared bucket (fake-gcs-server
# endpoint locally, real GCS in Cloud Run).
FROM python:3.13-slim

COPY mcp_servers/report/requirements.lock /tmp/report-requirements.lock
RUN pip install --no-cache-dir -r /tmp/report-requirements.lock

COPY shared/review_schemas/review_schemas /app/shared/review_schemas
COPY shared/mcp_ingress/mcp_ingress /app/shared/mcp_ingress
COPY mcp_servers/report/report_mcp /app/report_mcp
ENV PYTHONPATH=/app:/app/shared

# Build-time guard: dataset content must never ride along.
RUN ! find /app -path "*dataset/stories*" -o -path "*dataset/expected*" | grep -q .

# Run as non-root.
USER nobody

CMD ["python", "-m", "uvicorn", "report_mcp.main:application", "--host", "0.0.0.0", "--port", "8080"]
