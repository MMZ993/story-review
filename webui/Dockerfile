# Webui service image (Phase 7).
# Build context: repository root —
#   docker build -f webui/Dockerfile .
#
# Static shell + thin /api reverse proxy only (D17-1 + amendment): no
# business logic, no database, no dataset content (guard below).
FROM python:3.13-slim

COPY webui/requirements.lock /tmp/webui-requirements.lock
RUN pip install --no-cache-dir -r /tmp/webui-requirements.lock

COPY webui/webui /app/webui
COPY webui/static /app/static
ENV PYTHONPATH=/app

# Build-time guard: dataset content must never ride along.
RUN ! find /app -path "*dataset/stories*" -o -path "*dataset/expected*" | grep -q .

# Run as non-root.
USER nobody

CMD ["python", "-m", "uvicorn", "webui.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
