/**
 * Behavior tests for the orchestration API client (static/api.js):
 * - Idempotency-Key: fresh UUID v4 per logical request, persisted before the
 *   fetch fires, reused verbatim across 503 retries and on lost-response
 *   replay, cleared on completion.
 * - 503 retry: same key, same request, short backoff between attempts,
 *   bounded attempt count, error surfaced after exhaustion.
 * - Non-retryable errors (409, 404, 422): envelope parsed and returned, no
 *   retry, pending key cleared.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  abandonSession,
  clearPendingTurn,
  createSession,
  fetchReport,
  fetchSession,
  fetchSessions,
  fetchStories,
  fetchStoryDetail,
  finalizeRetry,
  getPendingTurn,
  postTurn,
  uuidv4,
} from "../../static/api.js";

/**
 * In-memory localStorage substitute with the Web Storage API surface.
 * jsdom provides localStorage, but an explicit stub keeps the tests
 * deterministic and independent of environment configuration.
 */
function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    clear: () => map.clear(),
    key: (i) => Array.from(map.keys())[i] ?? null,
    get length() {
      return map.size;
    },
  };
}

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

const errorEnvelope = (code, message, extra = {}) => ({ error: { code, message, ...extra } });

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("uuidv4", () => {
  it("produces the v4 shape (version and variant bits)", () => {
    const id = uuidv4();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });

  it("produces distinct ids", () => {
    expect(uuidv4()).not.toBe(uuidv4());
  });
});

describe("fetchStories", () => {
  it("GETs /api/v1/stories and returns the parsed body", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { stories: [{ id: "story-01" }] }));
    const result = await fetchStories({ fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/stories",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.ok).toBe(true);
    expect(result.body.stories[0].id).toBe("story-01");
  });

  it("returns the error envelope on a non-2xx response without retrying", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(503, errorEnvelope("ORCHESTRATION_UNREACHABLE", "down")),
      );
    const result = await fetchStories({ fetchImpl });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(503);
    expect(result.error.code).toBe("ORCHESTRATION_UNREACHABLE");
  });
});

describe("fetchStoryDetail", () => {
  it("GETs /api/v1/stories/{id}", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { id: "story-07" }));
    const result = await fetchStoryDetail("story-07", { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/stories/story-07",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.body.id).toBe("story-07");
  });
});

describe("fetchSession", () => {
  it("GETs /api/v1/sessions/{id} and returns the parsed SessionDetail", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { session_id: "s-1", turns: [] }));
    const result = await fetchSession("s-1", { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/sessions/s-1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.ok).toBe(true);
    expect(result.body.session_id).toBe("s-1");
  });

  it("returns the 404 envelope for an unknown session without retrying", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(404, errorEnvelope("SESSION_NOT_FOUND", "gone")),
      );
    const result = await fetchSession("s-1", { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.ok).toBe(false);
    expect(result.error.code).toBe("SESSION_NOT_FOUND");
  });
});

describe("postTurn idempotency-key handling", () => {
  it("POSTs the message with a UUID v4 key persisted per session before the fetch", async () => {
    const seenKeys = [];
    const storage = memoryStorage();
    const fetchImpl = vi.fn(async (_url, init) => {
      seenKeys.push(storage.getItem("pending:turn:s-1"));
      return jsonResponse(200, { session_id: "s-1", outcome: "continue" });
    });

    const result = await postTurn("s-1", { message: "hello" }, { fetchImpl, storage });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/sessions/s-1/turns",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.body).toBe(JSON.stringify({ message: "hello", po_accepted: false }));
    expect(seenKeys[0]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(init.headers["Idempotency-Key"]).toBe(seenKeys[0]);
    expect(storage.getItem("pending:turn:s-1")).toBeNull();
    expect(result.ok).toBe(true);
  });

  it("sends {po_accepted: true} without a message for the acceptance action", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { session_id: "s-1", outcome: "finalize" }));
    await postTurn("s-1", { poAccepted: true }, { fetchImpl, storage: memoryStorage() });
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.body).toBe(JSON.stringify({ po_accepted: true }));
  });

  it("re-uses a persisted pending turn key on lost-response replay", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { session_id: "s-1", outcome: "continue" }));
    const storage = memoryStorage();
    const storedKey = "11111111-2222-4333-8444-555555555555";
    storage.setItem("pending:turn:s-1", storedKey);

    await postTurn("s-1", { message: "again" }, { fetchImpl, storage });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["Idempotency-Key"]).toBe(storedKey);
    expect(storage.getItem("pending:turn:s-1")).toBeNull();
  });
});

describe("postTurn 503 retry and 409 no-retry", () => {
  it("retries a 503 with the same key and succeeds", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(503, errorEnvelope("RETRYABLE", "busy")))
      .mockResolvedValueOnce(jsonResponse(200, { session_id: "s-1", outcome: "continue" }));
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await postTurn("s-1", { message: "hi" }, {
      fetchImpl,
      storage: memoryStorage(),
      sleep,
      backoffMs: 50,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const [first, second] = fetchImpl.mock.calls;
    expect(second[1].headers["Idempotency-Key"]).toBe(first[1].headers["Idempotency-Key"]);
    expect(sleep).toHaveBeenCalledWith(50);
    expect(result.ok).toBe(true);
  });

  it.each([
    [409, "SESSION_READ_ONLY", "parked"],
    [422, "VALIDATION_ERROR", "empty message"],
    [422, "DELEGATION_VALIDATION", "bad delegation"],
  ])(
    "%i %s: returns the envelope without retrying and clears the key",
    async (status, code, message) => {
      const fetchImpl = vi
        .fn()
        .mockResolvedValue(jsonResponse(status, errorEnvelope(code, message)));
      const storage = memoryStorage();
      const sleep = vi.fn().mockResolvedValue(undefined);

      const result = await postTurn("s-1", { message: "hi" }, {
        fetchImpl,
        storage,
        sleep,
      });

      expect(fetchImpl).toHaveBeenCalledTimes(1);
      expect(result.ok).toBe(false);
      expect(result.error.code).toBe(code);
      expect(storage.getItem("pending:turn:s-1")).toBeNull();
    },
  );
});

describe("fetchReport", () => {
  it("GETs /api/v1/sessions/{id}/report and returns the parsed body", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { session_id: "s-1", report: [] }));
    const result = await fetchReport("s-1", { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/sessions/s-1/report",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.ok).toBe(true);
  });

  it("returns the 409 REPORT_NOT_READY envelope without retrying", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(409, errorEnvelope("REPORT_NOT_READY", "not completed")),
      );
    const result = await fetchReport("s-1", { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.error.code).toBe("REPORT_NOT_READY");
  });
});

describe("finalizeRetry", () => {
  it("POSTs an empty body with a persisted key under pending:finalize:{id}", async () => {
    const seenKeys = [];
    const storage = memoryStorage();
    const fetchImpl = vi.fn(async (_url, init) => {
      seenKeys.push(storage.getItem("pending:finalize:s-1"));
      return jsonResponse(200, { session_id: "s-1", report: [] });
    });

    const result = await finalizeRetry("s-1", { fetchImpl, storage });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/sessions/s-1/finalize",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.body).toBe("{}");
    expect(seenKeys[0]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(storage.getItem("pending:finalize:s-1")).toBeNull();
    expect(result.ok).toBe(true);
  });

  it("retries a 503 render failure with the same key (finalizing stays retryable)", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(503, errorEnvelope("RETRYABLE", "render failed")))
      .mockResolvedValueOnce(jsonResponse(200, { session_id: "s-1", report: [] }));
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await finalizeRetry("s-1", {
      fetchImpl,
      storage: memoryStorage(),
      sleep,
      backoffMs: 10,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const [first, second] = fetchImpl.mock.calls;
    expect(second[1].headers["Idempotency-Key"]).toBe(first[1].headers["Idempotency-Key"]);
    expect(result.ok).toBe(true);
  });

  it("returns a 409 NOT_FINALIZING envelope without retrying", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(409, errorEnvelope("NOT_FINALIZING", "active")));
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await finalizeRetry("s-1", {
      fetchImpl,
      storage: memoryStorage(),
      sleep,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.error.code).toBe("NOT_FINALIZING");
  });
});

describe("abandonSession", () => {
  it("POSTs an empty body with a persisted key under pending:abandon:{id}", async () => {
    const storage = memoryStorage();
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { session_id: "s-1", state: "parked" }));

    const result = await abandonSession("s-1", { fetchImpl, storage });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/sessions/s-1/abandon",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.body).toBe("{}");
    expect(init.headers["Idempotency-Key"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(storage.getItem("pending:abandon:s-1")).toBeNull();
    expect(result.ok).toBe(true);
    expect(result.body).toEqual({ session_id: "s-1", state: "parked" });
  });

  it("retries a 503 with the same key and returns a 409 SESSION_LOCKED envelope without clearing the key", async () => {
    const storage = memoryStorage();
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(503, errorEnvelope("RETRYABLE", "upstream")))
      .mockResolvedValueOnce(
        jsonResponse(409, errorEnvelope("SESSION_LOCKED", "lease held", { retry_after_seconds: 2 })),
      );
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await abandonSession("s-1", {
      fetchImpl,
      storage,
      sleep,
      backoffMs: 10,
      attempts: 2,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const [first, second] = fetchImpl.mock.calls;
    expect(second[1].headers["Idempotency-Key"]).toBe(first[1].headers["Idempotency-Key"]);
    expect(result.error.code).toBe("SESSION_LOCKED");
    expect(storage.getItem("pending:abandon:s-1")).toBe(
      first[1].headers["Idempotency-Key"],
    );
  });

  it("returns a definitive 409 SESSION_READ_ONLY without retrying", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(409, errorEnvelope("SESSION_READ_ONLY", "parked")));
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await abandonSession("s-1", {
      fetchImpl,
      storage: memoryStorage(),
      sleep,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.error.code).toBe("SESSION_READ_ONLY");
  });
});

describe("createSession idempotency-key handling", () => {
  it("sends a fresh UUID v4 Idempotency-Key header on POST /api/v1/sessions", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(201, { session_id: "s-1", state: "active" }),
      );
    const storage = memoryStorage();

    await createSession("story-07", { fetchImpl, storage });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Idempotency-Key"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });

  it("persists the key before the fetch fires and clears it after a 201", async () => {
    const seenPendingKeys = [];
    const storage = memoryStorage();
    const fetchImpl = vi.fn(async (_url, _init) => {
      seenPendingKeys.push(storage.getItem("pending:create-session"));
      return jsonResponse(201, { session_id: "s-1" });
    });

    await createSession("story-07", { fetchImpl, storage });

    expect(seenPendingKeys.length).toBe(1);
    expect(seenPendingKeys[0]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(storage.getItem("pending:create-session")).toBeNull();
  });

  it("re-uses a persisted pending key when one exists (lost-response replay)", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(201, { session_id: "s-1" }));
    const storage = memoryStorage();
    const storedKey = "11111111-2222-4333-8444-555555555555";
    storage.setItem("pending:create-session", storedKey);

    await createSession("story-07", { fetchImpl, storage });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["Idempotency-Key"]).toBe(storedKey);
  });
});

describe("createSession 503 retry", () => {
  it("retries the same request with the same Idempotency-Key after backoff", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(503, errorEnvelope("RETRYABLE", "lease busy")),
      )
      .mockResolvedValueOnce(
        jsonResponse(201, { session_id: "s-1", state: "active" }),
      );
    const storage = memoryStorage();
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await createSession("story-07", {
      fetchImpl,
      storage,
      sleep,
      backoffMs: 50,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const [first, second] = fetchImpl.mock.calls;
    expect(second[1].headers["Idempotency-Key"]).toBe(
      first[1].headers["Idempotency-Key"],
    );
    expect(sleep).toHaveBeenCalledWith(50);
    expect(result.ok).toBe(true);
    expect(result.body.session_id).toBe("s-1");
    expect(storage.getItem("pending:create-session")).toBeNull();
  });

  it("gives up after the attempt budget and reports the error", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(503, errorEnvelope("RETRYABLE", "down")));
    const storage = memoryStorage();
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await createSession("story-07", {
      fetchImpl,
      storage,
      sleep,
      backoffMs: 1,
      attempts: 3,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(503);
  });
});

describe("createSession non-retryable errors", () => {
  it.each([
    [409, "SESSION_ACTIVE", "story already has an active session"],
    [404, "STORY_NOT_FOUND", "unknown story"],
    [422, "VALIDATION_ERROR", "story_id must be a known story id"],
  ])(
    "%i %s: returns the envelope without retrying and clears the key",
    async (status, code, message) => {
      const fetchImpl = vi
        .fn()
        .mockResolvedValue(jsonResponse(status, errorEnvelope(code, message)));
      const storage = memoryStorage();
      const sleep = vi.fn().mockResolvedValue(undefined);

      const result = await createSession("story-07", {
        fetchImpl,
        storage,
        sleep,
      });

      expect(fetchImpl).toHaveBeenCalledTimes(1);
      expect(result.ok).toBe(false);
      expect(result.status).toBe(status);
      expect(result.error.code).toBe(code);
      expect(storage.getItem("pending:create-session")).toBeNull();
    },
  );
});

describe("pending-turn body persistence (refresh-resume)", () => {
  const SCOPE = "pending:turn:s-1";
  const BODY_SCOPE = `${SCOPE}:body`;

  async function drivePostTurn(storage, responses) {
    const calls = [...responses];
    const fetchImpl = vi.fn(async () => jsonResponse(200, calls.shift()));
    await postTurn(
      "s-1",
      { message: "hello" },
      { fetchImpl, storage, sleep: async () => {}, attempts: 1 },
    );
    return fetchImpl;
  }

  it("persists the turn body next to the idempotency key before the fetch", async () => {
    const storage = memoryStorage();
    const fetchImpl = vi.fn(async () => {
      expect(storage.getItem(SCOPE)).toMatch(/-/);
      expect(JSON.parse(storage.getItem(BODY_SCOPE))).toEqual({
        message: "hello",
        po_accepted: false,
      });
      return jsonResponse(200, { session_id: "s-1", turn_number: 2 });
    });
    await postTurn("s-1", { message: "hello" }, { fetchImpl, storage, attempts: 1 });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(storage.getItem(SCOPE)).toBeNull();
    expect(storage.getItem(BODY_SCOPE)).toBeNull();
  });

  it("keeps the pending body while a retryable 503 is pending", async () => {
    const storage = memoryStorage();
    let calls = 0;
    const fetchImpl = vi.fn(async () => {
      calls += 1;
      if (calls === 1) return jsonResponse(503, errorEnvelope("UPSTREAM_UNAVAILABLE", "x"));
      expect(storage.getItem(BODY_SCOPE)).not.toBeNull();
      return jsonResponse(200, { session_id: "s-1", turn_number: 2 });
    });
    await postTurn(
      "s-1",
      { message: "hello" },
      { fetchImpl, storage, sleep: async () => {}, attempts: 2 },
    );
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(storage.getItem(BODY_SCOPE)).toBeNull();
  });

  it("getPendingTurn reads the stored body; clearPendingTurn removes both keys", async () => {
    const storage = memoryStorage();
    storage.setItem(SCOPE, "22222222-2222-4222-8222-222222222222");
    storage.setItem(BODY_SCOPE, JSON.stringify({ message: "hi", po_accepted: false }));
    expect(getPendingTurn("s-1", { storage })).toEqual({
      message: "hi",
      poAccepted: false,
    });
    expect(getPendingTurn("s-9", { storage })).toBeNull();
    clearPendingTurn("s-1", { storage });
    expect(storage.getItem(SCOPE)).toBeNull();
    expect(storage.getItem(BODY_SCOPE)).toBeNull();
    expect(getPendingTurn("s-1", { storage })).toBeNull();
  });
});

describe("fetchSessions", () => {
  it("returns the session list envelope", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, {
        sessions: [
          {
            session_id: "s-1",
            story_id: "story-04",
            state: "active",
            processing_stage: "reviewing",
          },
        ],
        next_cursor: null,
      }),
    );
    const result = await fetchSessions({ fetchImpl });
    expect(result.ok).toBe(true);
    expect(result.body.sessions[0].processing_stage).toBe("reviewing");
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/sessions",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("SESSION_LOCKED replay retry", () => {
  it("retries a locked session with the SAME key, honoring retry_after_seconds", async () => {
    const storage = memoryStorage();
    const sleep = vi.fn(async () => {});
    const calls = [
      jsonResponse(409, {
        error: {
          code: "SESSION_LOCKED",
          message: "lease held",
          retry_after_seconds: 30,
        },
      }),
      jsonResponse(200, { session_id: "s-1", turn_number: 3 }),
    ];
    const keys = [];
    const fetchImpl = vi.fn(async (url, request) => {
      keys.push(request.headers["Idempotency-Key"]);
      return calls.shift() ?? jsonResponse(200, {});
    });
    const result = await postTurn("s-1", { message: "hi" }, {
      fetchImpl,
      storage,
      sleep,
      attempts: 3,
    });
    expect(result.ok).toBe(true);
    expect(keys[0]).toBe(keys[1]);
    expect(sleep).toHaveBeenCalledWith(30000);
    expect(storage.getItem("pending:turn:s-1")).toBeNull();
  });

  it("keeps the pending key and body when the locked-retry budget is exhausted", async () => {
    // The logical request may still be executing server-side (e.g. a
    // delegated turn under its lease after a mid-turn reload): the key and
    // body must survive for a later resume/replay instead of being cleared
    // as if the request were definitively rejected.
    const storage = memoryStorage();
    const sleep = vi.fn(async () => {});
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "SESSION_LOCKED",
          message: "lease held",
          retry_after_seconds: 1,
        },
      }),
    );

    const result = await postTurn("s-1", { message: "hi" }, {
      fetchImpl,
      storage,
      sleep,
      attempts: 2,
      backoffMs: 5,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(result.ok).toBe(false);
    expect(result.error.code).toBe("SESSION_LOCKED");
    expect(storage.getItem("pending:turn:s-1")).not.toBeNull();
    expect(getPendingTurn("s-1", { storage })).toEqual({
      message: "hi",
      poAccepted: false,
    });
  });
});
