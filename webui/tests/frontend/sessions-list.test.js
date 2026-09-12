/**
 * Behavior tests for the open-sessions list (static/sessions-list.js):
 * only active sessions are listed with their story title (fallback id),
 * a processing stage is shown, resume buttons report their session id,
 * and an empty/open-session-free list renders an explicit note.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";

import { renderOpenSessions } from "../../static/sessions-list.js";

function installDom() {
  const { window } = new JSDOM(
    `<!doctype html><body>
      <details id="open-sessions"><summary id="open-sessions-summary"></summary>
      <ul id="open-sessions-list"></ul></details>`,
  );
  globalThis.document = window.document;
  return {
    summary: window.document.querySelector("#open-sessions-summary"),
    list: window.document.querySelector("#open-sessions-list"),
  };
}

const session = (overrides = {}) => ({
  session_id: "sess-1",
  story_id: "story-07",
  state: "active",
  processing_stage: null,
  ...overrides,
});

describe("renderOpenSessions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists active sessions with story titles and a resume button", () => {
    const dom = installDom();
    const onResume = vi.fn();
    renderOpenSessions(
      dom.list,
      dom.summary,
      [session(), session({ session_id: "sess-2", state: "completed" })],
      [{ story_id: "story-07", title: "30-minute order edit window after purchase" }],
      onResume,
    );

    expect(dom.summary.textContent).toBe("open sessions (1)");
    const rows = dom.list.querySelectorAll("li");
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("story-07");
    expect(rows[0].textContent).toContain("30-minute order edit window after purchase");

    rows[0].querySelector("button").click();
    expect(onResume).toHaveBeenCalledWith("sess-1");
  });

  it("falls back to the story id when no title is known", () => {
    const dom = installDom();
    renderOpenSessions(dom.list, dom.summary, [session()], [], vi.fn());
    expect(dom.list.querySelector("li").textContent).toContain("story-07");
  });

  it("annotates a session that is currently processing", () => {
    const dom = installDom();
    renderOpenSessions(
      dom.list,
      dom.summary,
      [session({ processing_stage: "delegating" })],
      [],
      vi.fn(),
    );
    expect(dom.list.querySelector("li").textContent).toContain("delegating");
  });

  it("renders an explicit note when there are no open sessions", () => {
    const dom = installDom();
    renderOpenSessions(dom.list, dom.summary, [], [], vi.fn());
    expect(dom.summary.textContent).toBe("open sessions (0)");
    expect(dom.list.textContent).toContain("no open sessions");
  });

  it("renders the note when the sessions fetch failed (null list)", () => {
    const dom = installDom();
    renderOpenSessions(dom.list, dom.summary, null, [], vi.fn());
    expect(dom.list.textContent).toContain("no open sessions");
  });
});
