# Story MCP server image (Phase 4, D10).
# Build context: repository root —
#   docker build -f mcp_servers/story/Dockerfile .
#
# Dataset-agnostic by construction: no story or expected content enters the
# image (enforced by the check below); the mock source loads its data at
# startup from STORY_DATASET_LOCATION (directory or gs:// URI). The image
# ships three code-only local packages: story_mcp, review_schemas, and
# ado_wire, plus dataset_loader (code-only: the export-envelope parser the
# mock source reuses — never dataset content).
FROM python:3.13-slim

COPY mcp_servers/story/requirements.lock /tmp/story-requirements.lock
RUN pip install --no-cache-dir -r /tmp/story-requirements.lock

COPY shared/review_schemas/review_schemas /app/shared/review_schemas
COPY shared/mcp_ingress/mcp_ingress /app/shared/mcp_ingress
COPY shared/ado_wire/ado_wire /app/shared/ado_wire
COPY dataset/loader/dataset_loader /app/dataset/dataset_loader
COPY mcp_servers/story/story_mcp /app/story_mcp
ENV PYTHONPATH=/app:/app/shared:/app/dataset

# Build-time guard: dataset content must never ride along.
RUN ! find /app -path "*dataset/stories*" -o -path "*dataset/expected*" | grep -q .

# Run as non-root.
USER nobody

CMD ["python", "-m", "uvicorn", "story_mcp.main:application", "--host", "0.0.0.0", "--port", "8080"]
