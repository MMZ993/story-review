# Local agent-adapter image (Phase 5, `local-agents` compose profile).
# Build context: repository root, one image per adapter slug —
#   docker build --build-arg SLUG=facilitator \
#     -f deploy/compose/adapters/Dockerfile .
#
# Ships four code-only local packages (review_schemas, agent_kit, the
# agent, the adapter binding) plus the repo `prompts/` static data mounted
# at /app/prompts (PROMPTS_DIR). No dataset content enters the image
# (guard below); Vertex credentials come from the bind-mounted ADC file in
# the compose profile, never from the image.
ARG SLUG
FROM python:3.13-slim
ARG SLUG
ENV PYTHONPATH=/app
# google-adk extras: mcp = McpToolset, db = DatabaseSessionService; asyncpg
# is the PostgreSQL driver for the session backend; uvicorn serves the shell.
RUN pip install --no-cache-dir "google-adk[mcp,db]==2.8.0" asyncpg uvicorn

COPY shared/review_schemas /tmp/src/review_schemas
COPY shared/agent_kit /tmp/src/agent_kit
COPY agents/${SLUG} /tmp/src/${SLUG}
COPY deploy/compose/adapters/${SLUG} /tmp/src/adapter
RUN pip install --no-cache-dir /tmp/src/review_schemas /tmp/src/agent_kit \
    /tmp/src/${SLUG} /tmp/src/adapter && rm -rf /tmp/src

COPY prompts /app/prompts
ENV PROMPTS_DIR=/app/prompts

# Build-time guard: dataset content must never ride along.
RUN ! find /app -path "*dataset/stories*" -o -path "*dataset/expected*" | grep -q .

# Run as non-root.
USER nobody

# SLUG stays in the environment so the entrypoint can derive the adapter
# package name (e.g. business-reviewer -> business_reviewer_adapter).
ENV SLUG=${SLUG}
CMD ["sh", "-c", "pkg=$(echo $SLUG | tr - _)_adapter; exec python -m uvicorn $pkg:create_app --factory --host 0.0.0.0 --port 8080"]
