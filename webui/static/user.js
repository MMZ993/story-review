/**
 * Anonymous user identity (D24-3, api-contract.md "X-User-Id").
 *
 * The client generates one UUID v4 user id, persists it in a 90-day
 * cookie, and refreshes the cookie on every visit (sliding expiry).
 * Losing it means losing access to prior sessions — a new id starts an
 * empty history; multiple browsers get independent users. There is no
 * authentication: the id is an opaque grouping key the server scopes
 * sessions and story runs by.
 *
 * The cookie jar is injectable for deterministic tests; the default jar
 * reads and writes `document.cookie` (same-origin, no path/host scoping
 * needed beyond the app itself).
 */

import { uuidv4 } from "./api.js";

const COOKIE_NAME = "sr_user";
/** 90-day sliding window (D24-3). */
const MAX_AGE_SECONDS = 90 * 24 * 60 * 60;

/** RFC 4122 version-4 shape (lowercase; the server validates too). */
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

/** Parse one cookie value by name from a `name=value; …` string. */
export function readCookie(jarSource, name) {
  for (const part of jarSource.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

/**
 * The persisted user id, or null when absent or malformed. Pure read —
 * never mints or refreshes (callers that must not write use this).
 */
export function peekUserId(jar = cookieSource()) {
  const value = readCookie(jar, COOKIE_NAME);
  return value !== null && UUID_V4.test(value) ? value : null;
}

/** The current cookie string, or "" where no DOM exists (node tests). */
function cookieSource() {
  return globalThis.document?.cookie ?? "";
}

/**
 * The `secure` cookie attribute when the origin is HTTPS — set on the
 * public TLS deploy (Cloudflare → Cloud Run), omitted on the plain-HTTP
 * local compose origin where it would make the cookie unwritable.
 */
function secureAttribute() {
  return globalThis.location?.protocol === "https:" ? "; secure" : "";
}

/**
 * The user id for this client: the valid persisted one, or a freshly
 * minted UUID v4. Every call rewrites the cookie, sliding the 90-day
 * expiry forward (api-contract: "long-lived, refreshed on visit"). An
 * invalid stored value is replaced by a fresh id.
 */
export function ensureUserId(jar = cookieSource()) {
  const existing = peekUserId(jar);
  const userId = existing ?? uuidv4();
  // No-op outside a DOM (e.g. node-run unit tests): the id is still
  // returned, just not persisted across those calls.
  if (globalThis.document) {
    globalThis.document.cookie = `${COOKIE_NAME}=${userId}; max-age=${MAX_AGE_SECONDS}; path=/; samesite=lax${secureAttribute()}`;
  }
  return userId;
}
