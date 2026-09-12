/**
 * Behavior tests for the anonymous user identity (static/user.js, D24-3):
 * a UUID v4 persisted in a 90-day sliding cookie — minted once, retained
 * across visits, replaced when malformed, refreshed on every visit; and
 * the API client attaches it as X-User-Id on every call.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";

import { ensureUserId, peekUserId, readCookie } from "../../static/user.js";
import { fetchStories, postTurn } from "../../static/api.js";

// The module under test defaults to the global DOM's cookie jar; give the
// node-run tests a real jsdom document.
const dom = new JSDOM("", { url: "https://webui.local/" });
globalThis.document = dom.window.document;

const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

/** Minimal storage stub (the pending-key persistence seam). */
function fakeStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

const VALID = "12345678-1234-4123-8123-123456789abc"; // v4 shape (4xxx/8)

beforeEach(() => {
  // jsdom cannot "clear" cookies by assignment; max-age=0 deletes the key.
  document.cookie = "sr_user=; max-age=0; path=/";
});

describe("readCookie", () => {
  it("finds the named value among several cookies", () => {
    expect(readCookie("a=1; sr_user=x; b=2", "sr_user")).toBe("x");
  });

  it("returns null when absent", () => {
    expect(readCookie("a=1", "sr_user")).toBeNull();
  });
});

describe("peekUserId", () => {
  it("returns the persisted valid id without writing", () => {
    document.cookie = `sr_user=${VALID}`;
    expect(peekUserId()).toBe(VALID);
  });

  it("returns null for a missing or malformed id", () => {
    expect(peekUserId()).toBeNull();
    document.cookie = "sr_user=not-a-uuid";
    expect(peekUserId()).toBeNull();
    document.cookie = "sr_user=12345678-1234-1234-1234-123456789abc"; // v1
    expect(peekUserId()).toBeNull();
  });
});

describe("ensureUserId", () => {
  it("mints a UUID v4 and persists it in the cookie", () => {
    const id = ensureUserId();
    expect(id).toMatch(UUID_V4);
    expect(document.cookie).toContain(`sr_user=${id}`);
  });

  it("retains a valid persisted id (same user across visits)", () => {
    document.cookie = `sr_user=${VALID}`;
    expect(ensureUserId()).toBe(VALID);
  });

  it("replaces a malformed stored value with a fresh v4", () => {
    document.cookie = "sr_user=garbage";
    const id = ensureUserId();
    expect(id).toMatch(UUID_V4);
    expect(peekUserId()).toBe(id);
  });

  it("rewrites the cookie on every call (90-day sliding refresh)", () => {
    const first = ensureUserId();
    const spy = vi.spyOn(document, "cookie", "set");
    const second = ensureUserId();
    expect(second).toBe(first);
    expect(spy).toHaveBeenCalled(); // expiry slid forward
    spy.mockRestore();
  });
});

describe("api client X-User-Id", () => {
  it("GET /stories carries the user header", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ stories: [] }),
    });
    await fetchStories({ fetchImpl, getUserId: () => VALID });
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["X-User-Id"]).toBe(VALID);
  });

  it("POST turn carries the user header next to the idempotency key", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: "s", turn_number: 2 }),
    });
    await postTurn(
      "sess-x",
      { message: "hi" },
      { fetchImpl, storage: fakeStorage(), getUserId: () => VALID },
    );
    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["X-User-Id"]).toBe(VALID);
    expect(init.headers["Idempotency-Key"]).toMatch(UUID_V4);
  });
});
