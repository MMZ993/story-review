# Runbook 13 — Web UI (Phase 7)

Environment: owner's main PC (ADC + Vertex available; compose stack local).
Cloud SQL stays STOPPED throughout Phase 7 — orchestration state lives in the
compose `postgres` substitute, as in Phase 6. Plan:
`docs-local/plans/phase-7-webui.md`; decisions D16, D17 (+ amendment 1).

Verification-state log (append-only):

## Increment 0 — skeleton: package, static shell, /api proxy, tests, compose

**Status: COMPLETE (session 40, 2026-09-15; browser gate PASS).**

Owner decision opening the phase (**D17 amendment 1**): D17-1's "browser
calls orchestration directly" is unworkable (no CORS on orchestration, D16
forbids adding it; no persistent orchestration endpoint existed). The webui
app gains a thin same-origin `/api` reverse proxy (chosen for its fit to the
GCP deployment shape: one HTTPS LB path-routing `/api` → orchestration);
orchestration becomes a compose service as the proxy target. Recorded in
local-decisions.md.

Commands run (all local, no cloud actions, Cloud SQL STOPPED):

    make webui-test    # 7 passed (uv package) + 2 passed (vitest)
    docker build -f webui/Dockerfile -t webui-dev-test .        # ok
    docker run --rm -d --name webui-smoke -p 127.0.0.1:8121:8080 \
      -e ORCHESTRATION_BASE_URL=http://127.0.0.1:1 webui-dev-test
    curl -s http://127.0.0.1:8121/health           # {"status":"ok"}
    curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8121/   # 200
    curl -s http://127.0.0.1:8121/api/health
    # -> 503 ORCHESTRATION_UNREACHABLE (retryable) — proxy error path ok
    for p in / /app.js /app.css /markdown.js /vendor/marked.esm.js; do
      curl -s -o /dev/null -w "$p %{http_code}\n" http://127.0.0.1:8121$p;
    done   # all 200
    docker rm -f webui-smoke && docker rmi webui-dev-test        # cleaned up

Delivered:
- `webui/` uv package 0.1.0: `config.py` (strict env, single mandatory
  `ORCHESTRATION_BASE_URL`), `main.py` (app factory: `/health` liveness,
  static shell at `/`, `/api/{path}` pass-through proxy — method/path/query/
  body + Content-Type/Idempotency-Key/X-Correlation-Id forwarded, upstream
  status/body/correlation-id returned, `ORCHESTRATION_UNREACHABLE` retryable
  503 on connection errors).
- `webui/static/`: `index.html` (increment-0 shell: header with live
  orchestration status line, picker/session placeholders, import map),
  `app.js` (loads `/api/health`, displays reachability), `app.css` (minimal
  usability), `markdown.js` (carried over unchanged from cv-agent per
  D16-3/D17-3), `vendor/` (dompurify 3.4.13 / marked 18.0.9 / remend 1.3.0
  ESM dist files — the libraries' real source, vendored, no bundler).
- Tests: `webui/tests/test_app.py` (7 — health, static root, config
  strictness, GET/POST proxy forwarding incl. key header + query, upstream
  status/error-envelope passthrough, unreachable→503) with an httpx
  MockTransport upstream; `webui/tests/frontend/markdown.test.js` (2 —
  carried-over sanitizer tests, links de-fanged for the capstone context).
- `webui/package.json` + lock (dev-only vitest+jsdom; `node_modules/`
  gitignored), `webui/Dockerfile` (root-context, dataset guard, non-root),
  Makefile `webui-test` target, `.gitignore` node_modules entry.
- Compose: `webui` service (`local` profile, host port
  `127.0.0.1:${WEBUI_PORT:-8120}`, proxies to `http://orchestration:8080`);
  `orchestration` service (`local-agents` profile, host port
  `127.0.0.1:${ORCHESTRATION_PORT:-8130}`, compose-postgres DSN, compose
  service URLs, ADC bind mount like the adapters, `ORCH_GCS_PUBLIC_URL` →
  fake-gcs HTTPS host port).

Gotchas learned:
- **Compose Postgres namespace clash**: the default database in the compose
  postgres is the facilitator's ADK session backend, which already owns a
  `sessions` table — orchestration migration 0001 (`create table if not
  exists sessions`) silently skips it and then fails on a `turns` FK
  (`column "session_id" ... does not exist`). Fix: orchestration uses a
  **separate `orchestration` database** in the same container (compose
  `ORCH_DB_DSN` updated; `createdb` before first migration run).
- **MCP 421 in-network**: with `*_SERVICE_URL` unset, the MCP SDK's
  DNS-rebinding protection defaults the app host to `127.0.0.1` and rejects
  any other Host header with 421 — so in-network calls like
  `http://story:8080/mcp` (Host `story:8080`) fail while host-port calls
  (`127.0.0.1:8101`) pass (why the Phase 6 host-side gates never saw it).
  Fix: compose sets `STORY/ARTIFACT/REPORT_SERVICE_URL` to the in-network
  URLs (host then matches → protection does not auto-enable; harmless since
  local auth is disabled). In Cloud Run these are set anyway (audience), so
  this is local-only.
- Orchestration's `/health` lives **outside** the `/api` prefix — the webui
  status probe uses `GET /api/v1/stories?limit=1` (real readiness signal)
  instead of a health path.
- Orchestration (compose service) crashes at startup if its database does
  not exist yet — create the DB + run migrations **before** the first
  `agents-compose-up` that includes it (ordering in the gate commands
  below).
- `StaticFiles(html=True)` mounted at `/` serves assets at their bare paths
  (`/app.js`, not `/static/app.js`) — index.html references use the bare
  form.
- Makefile recipe already `cd webui` — `npm --prefix webui` inside it
  resolves to `webui/webui` (silent wrong-directory failure); run npm
  without the prefix after the cd.
- httpx `MockTransport` handlers must use `httpx.Response(...)`; requests
  expose `.content` (no `.json()` helper).

Browser gate (owner-driven, D17-5) — **PASS** (2026-09-15):

    # one-time database setup (idempotent thereafter):
    docker compose --profile local --profile local-agents --env-file env/.env \
      exec -T postgres createdb -U facilitator orchestration
    docker run --rm --network story-review_default \
      -v "$PWD/deploy/cloud-sql:/m:ro" \
      -e DATABASE_URL=postgres://facilitator:facilitator@postgres:5432/orchestration \
      postgres:16 bash /m/run-migrations.sh
    make agents-compose-up   # brings up the full stack incl. orchestration + webui

Host-side checks before handing over: `curl 127.0.0.1:8130/health` →
{"status":"ok"} with all four dependencies reachable;
`curl -o /dev/null -w %{http_code} 127.0.0.1:8120/api/v1/stories` → 200.
Owner in the browser at `http://127.0.0.1:8120/`: page loads, header shows
**"orchestration: reachable"** (verbatim report in chat). Stack left up for
the increment-1 session; `agents-compose-down` when done with it.

Increment-0 independent review (fresh read-only subagent, after the browser
gate): **1 Critical + 1 Important + minors — all fixed in-session.**

- **Critical**: the proxy's httpx client used the default 5 s timeout — a
  long turn (up to the 5-minute request deadline) would surface as a
  retryable `ORCHESTRATION_UNREACHABLE` 503 while orchestration is still
  processing, inviting a same-key retry against the live turn. Fixed:
  `timeout=httpx.Timeout(None)` (server deadline governs) + a pinning test.
- **Important**: `/api/%2e%2e/health` (raw dot-segment traversal) escaped
  the /api scope via httpx path normalization. Fixed: normpath guard → 404
  (+ test). Gotcha: curl *without* `--path-as-is` decodes/normalizes such
  paths client-side, so manual checks must use `--path-as-is` to exercise
  the guard (verified live: 404).
- Minors fixed: misleading `/health` docstring (orchestration health is
  outside /api); new tests pinning the forwarded-header allowlist
  (Cookie/Authorization/arbitrary client headers are never forwarded) and
  405 for non-forwarded methods. Deferred minor: `npm ci` in `webui-test`
  hits the registry (dev-only tooling per D17-2 — acceptable).

Post-fix verification: `make webui-test` **11 passed + 2 vitest passed**;
webui container rebuilt and live: `GET /api/v1/stories?limit=1` via proxy
→ 200, raw traversal → 404; compose contract **20 passed** (regression).
