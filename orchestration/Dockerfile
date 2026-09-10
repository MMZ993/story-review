# Orchestration service image (Phase 6).
# Build context: repository root —
#   docker build -f orchestration/Dockerfile .
#
# No dataset content is ever involved (guard below); orchestration state lives
# in the configured database (compose Postgres substitute locally, Cloud SQL
# in deployment) and artifacts/reports in the configured bucket.
FROM python:3.13-slim

COPY orchestration/requirements.lock /tmp/orchestration-requirements.lock
RUN pip install --no-cache-dir -r /tmp/orchestration-requirements.lock

COPY shared/review_schemas/review_schemas /app/shared/review_schemas
COPY orchestration/orchestration /app/orchestration
ENV PYTHONPATH=/app:/app/shared

# Build-time guard: dataset content must never ride along.
RUN ! find /app -path "*dataset/stories*" -o -path "*dataset/expected*" | grep -q .

# Run as non-root.
USER nobody

CMD ["python", "-m", "uvicorn", "orchestration.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
