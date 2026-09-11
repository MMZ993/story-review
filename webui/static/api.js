/**
 * Orchestration API client (D17-3: written fresh against api-contract.md).
 *
 * All calls go through the webui's same-origin /api reverse proxy, so no
 * absolute host is needed. Mutating POSTs carry an Idempotency-Key header
 * (UUID v4); the key of the in-flight logical request is persisted to
 * localStorage before the fetch fires (client rule: persist the
 * idempotency key with the in-flight logical request) so a lost response
 * can be replayed safely on the next attempt or page load.
 *
 * Retry policy (client rules): a 503 response is retried with the SAME
 * key and request after a short backoff, up to a bounded attempt budget;
 * every other status is returned to the caller as-is — the UI decides how
 * to present 409/404/422 envelopes and never auto-hammers non-retryable
 * errors.
 *
 * The module has no DOM dependencies; `fetchImpl`, `storage`, `sleep`,
 * `backoffMs` and `attempts` are injectable for deterministic tests.
 */

const STORIES_URL = "/api/v1/stories";
const SESSIONS_URL = "/api/v1/sessions";

const DEFAULT_ATTEMPTS = 5;
const DEFAULT_BACKOFF_MS = 2000;

/**
 * RFC 4122 version 4 identifier. Crypto-random when the browser provides
 * crypto.getRandomValues; the math fallback only runs in environments
 * without WebCrypto.
 */
export function uuidv4() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC variant
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Normalized outcome of one request: ok + parsed body on 2xx; otherwise
 * ok:false with the HTTP status and the parsed error envelope
 * ({error:{code,message}}), or a TRANSPORT error when fetch itself threw.
 */
async function toResult(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  return response.ok
    ? { ok: true, status: response.status, body }
    : { ok: false, status: response.status, error: body?.error ?? null };
}

/** GET the story list (dataset-bounded; optional title filter). */
export async function fetchStories(
  options = {},
  { filter } = {},
) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const url = filter ? `${STORIES_URL}?filter=${encodeURIComponent(filter)}` : STORIES_URL;
  try {
    return toResult(await fetchImpl(url, { method: "GET" }));
  } catch {
    return { ok: false, status: 0, error: { code: "TRANSPORT", message: "request failed" } };
  }
}

/** GET one story's detail (epic/roadmap context, comments) for the preview. */
export async function fetchStoryDetail(storyId, options = {}) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  try {
    return toResult(
      await fetchImpl(`${STORIES_URL}/${encodeURIComponent(storyId)}`, {
        method: "GET",
      }),
    );
  } catch {
    return { ok: false, status: 0, error: { code: "TRANSPORT", message: "request failed" } };
  }
}

/**
 * Shared mutating-POST core: persists the logical request's idempotency
 * key under `scope` before the first fetch, retries 503 with the SAME key
 * and request after a backoff up to the attempt budget, and clears the
 * pending key once any definitive outcome (2xx or non-503) is received.
 * Transport failures are definitive (the key stays for later replay only if
 * the caller never completes — it is cleared here because the client shows
 * the transport error; a re-send generates a fresh logical request).
 */
async function postWithIdempotentKey(url, body, scope, options) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const storage = options.storage ?? globalThis.localStorage;
  const sleep = options.sleep ?? defaultSleep;
  const attempts = options.attempts ?? DEFAULT_ATTEMPTS;
  const backoffMs = options.backoffMs ?? DEFAULT_BACKOFF_MS;

  const key = storage.getItem(scope) ?? uuidv4();
  storage.setItem(scope, key);
  const request = {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(body),
  };

  let result;
  for (let attempt = 1; ; attempt += 1) {
    let response;
    try {
      response = await fetchImpl(url, request);
    } catch {
      result = { ok: false, status: 0, error: { code: "TRANSPORT", message: "request failed" } };
      break;
    }
    result = await toResult(response);
    if (result.ok || result.status !== 503 || attempt >= attempts) break;
    await sleep(backoffMs);
  }

  storage.removeItem(scope);
  return result;
}

/** GET one session's detail (state, turn history, artifact references). */
export async function fetchSession(sessionId, options = {}) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  try {
    return toResult(
      await fetchImpl(`${SESSIONS_URL}/${encodeURIComponent(sessionId)}`, {
        method: "GET",
      }),
    );
  } catch {
    return { ok: false, status: 0, error: { code: "TRANSPORT", message: "request failed" } };
  }
}

/**
 * POST /api/v1/sessions/{id}/turns (flow 2): one PO dialogue action.
 * Body: {message, po_accepted:false} for a message, or {po_accepted:true}
 * for the explicit acceptance action (contract: no message on acceptance).
 * Idempotency: one pending key per session ("pending:turn:{id}" — exactly
 * one in-flight logical request per session), persisted before the fetch,
 * re-used on 503 retry and lost-response replay, cleared on any definitive
 * outcome. 409/404/422 are definitive and returned to the caller.
 */
export async function postTurn(sessionId, { message, poAccepted = false }, options = {}) {
  const body = poAccepted ? { po_accepted: true } : { message, po_accepted: false };
  return postWithIdempotentKey(
    `${SESSIONS_URL}/${encodeURIComponent(sessionId)}/turns`,
    body,
    `pending:turn:${sessionId}`,
    options,
  );
}

/**
 * POST /api/v1/sessions/{id}/finalize (flow-3 retry): reacquire + render
 * + complete a finalizing session, or replay the persisted report for a
 * completed one. Empty body + Idempotency-Key (scope per session); a 503
 * render failure stays retryable with the same key. 409 NOT_FINALIZING /
 * SESSION_READ_ONLY are definitive and returned to the caller.
 */
export async function finalizeRetry(sessionId, options = {}) {
  return postWithIdempotentKey(
    `${SESSIONS_URL}/${encodeURIComponent(sessionId)}/finalize`,
    {},
    `pending:finalize:${sessionId}`,
    options,
  );
}

/** GET /api/v1/sessions/{id}/report: regenerate signed URLs (completed only). */
export async function fetchReport(sessionId, options = {}) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  try {
    return toResult(
      await fetchImpl(`${SESSIONS_URL}/${encodeURIComponent(sessionId)}/report`, {
        method: "GET",
      }),
    );
  } catch {
    return { ok: false, status: 0, error: { code: "TRANSPORT", message: "request failed" } };
  }
}

/**
 * POST /api/v1/sessions (flow 1): select a story and open the dialogue.
 * Body: {story_id, requested_formats} (contract requires a non-empty
 * format list; the picker offers none, so both formats are requested).
 * Idempotency: a pending key for the "create-session" logical request is
 * persisted before the first fetch and re-used on every retry and on a
 * later invocation (lost-response replay); it is cleared once the request
 * completes with any definitive outcome. 503 is retried with the same key;
 * all other statuses (201, 404 unknown story, 409 SESSION_ACTIVE, 422) are
 * definitive and returned to the caller.
 */
export async function createSession(storyId, options = {}) {
  const formats = options.requestedFormats ?? ["md", "pdf"];
  return postWithIdempotentKey(
    SESSIONS_URL,
    { story_id: storyId, requested_formats: formats },
    "pending:create-session",
    options,
  );
}
