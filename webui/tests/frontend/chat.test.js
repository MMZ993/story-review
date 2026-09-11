/**
 * Behavior tests for the session chat view (static/chat.js):
 * - History replay from SessionDetail: PO bubbles right, facilitator
 *   markdown left, meta line (issues/synthesis/outcome).
 * - Resume routing: 404 hands back to the caller; success opens the view.
 * - sendTurn: optimistic PO bubble, single in-flight request, composer
 *   disabled while processing, park outcome disables further input,
 *   409 SESSION_LOCKED shows the retry hint without re-sending.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";

vi.mock("../../static/api.js", () => ({
  fetchSession: vi.fn(),
  postTurn: vi.fn(),
  fetchReport: vi.fn(),
  finalizeRetry: vi.fn(),
}));

import { openSession } from "../../static/chat.js";
import { fetchReport, fetchSession, finalizeRetry, postTurn } from "../../static/api.js";

const SESSION_VIEW_HTML = `
<section id="picker-view" hidden></section>
<section id="session-view">
  <p id="session-header"></p>
  <ol id="messages"></ol>
  <form id="composer"><textarea id="turn-input"></textarea><button id="send-turn" type="submit">send</button><button id="accept-turn" type="button" hidden>accept &amp; finalize</button></form>
  <div id="session-actions"></div>
  <div id="report-links"></div>
  <div id="status"></div>
</section>`;

function installDom() {
  const { window } = new JSDOM(`<!doctype html><body>${SESSION_VIEW_HTML}</body>`);
  globalThis.document = window.document;
}

const turn = (overrides = {}) => ({
  turn_number: 2,
  po_message: "the API limit is 100 rps",
  po_accepted: false,
  facilitator_reply: "**review** updated",
  delegation: { open_issues: ["limit", "quota"] },
  resolutions: [],
  outcome: "continue",
  produced_artifacts: [{ type: "synthesis", artifact_id: "art-1", version: 2 }],
  ...overrides,
});

const sessionDetail = (turns, state = "active") => ({
  session_id: "s-1",
  story_id: "story-04",
  state,
  facilitator_turn_count: 2,
  turns,
});

const reportDownload = (format = "md") => ({
  reference: { type: `report-${format}`, artifact_id: `art-r-${format}` },
  format,
  signed_url: `https://127.0.0.1:9026/x/report.${format}?sig=1`,
  expires_at: "2026-09-15T20:00:00Z",
});

const ok = (body) => ({ ok: true, status: 200, body });

beforeEach(() => {
  vi.clearAllMocks();
  installDom();
});

describe("openSession history replay", () => {
  it("renders PO messages, facilitator markdown, and a meta line", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));

    await openSession("s-1");

    const messages = [...document.querySelectorAll("#messages li")];
    expect(messages[0].className).toBe("message-user");
    expect(messages[0].textContent).toBe("the API limit is 100 rps");
    expect(messages[1].className).toBe("message-assistant");
    expect(messages[1].querySelector("strong")?.textContent).toBe("review");
    expect(messages[2].textContent).toBe(
      "turn 2 — open issues: 2 · synthesis: art-1 v2 · outcome: continue",
    );
    expect(document.querySelector("#session-header").textContent).toContain(
      "story-04 — active — facilitator turns 2/10",
    );
    expect(document.querySelector("#session-view").hidden).toBe(false);
    expect(document.querySelector("#turn-input").disabled).toBe(false);
  });

  it("renders an acceptance turn as an explicit PO action bubble", async () => {
    fetchSession.mockResolvedValue(
      ok(sessionDetail([turn({ po_message: null, po_accepted: true })])),
    );

    await openSession("s-1");

    expect(document.querySelector("#messages li").textContent).toBe(
      "(accepted the report)",
    );
  });

  it("disables the composer for a parked session", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()], "parked")));

    await openSession("s-1");

    expect(document.querySelector("#send-turn").disabled).toBe(true);
    expect(document.querySelector("#status").textContent).toContain("parked");
  });
});

describe("openSession failure routing", () => {
  it("calls onUnknownSession and returns false on 404", async () => {
    fetchSession.mockResolvedValue({
      ok: false,
      status: 404,
      error: { code: "SESSION_NOT_FOUND", message: "unknown session" },
    });
    const onUnknownSession = vi.fn();

    const opened = await openSession("s-1", { onUnknownSession });

    expect(opened).toBe(false);
    expect(onUnknownSession).toHaveBeenCalledTimes(1);
  });
});

describe("sendTurn", () => {
  it("sends one turn, renders the reply, and disables input while in flight", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1");
    const input = document.querySelector("#turn-input");
    const send = document.querySelector("#send-turn");

    let resolveTurn;
    postTurn.mockReturnValue(
      new Promise((resolve) => {
        resolveTurn = resolve;
      }),
    );
    input.value = "  checked with ops  ";
    send.click();

    expect(input.disabled).toBe(true);
    expect(send.disabled).toBe(true);
    expect(document.querySelector("#status").textContent).toContain("processing");
    const bubbles = [...document.querySelectorAll("#messages .message-user")];
    expect(bubbles.at(-1).textContent).toBe("checked with ops");
    expect(postTurn).toHaveBeenCalledWith(
      "s-1",
      { message: "checked with ops" },
    );

    resolveTurn(
      ok({
        session_id: "s-1",
        turn_number: 3,
        outcome: "continue",
        state: "active",
        facilitator_reply: "noted",
        issues: ["limit"],
      }),
    );
    await vi.waitFor(() =>
      expect(document.querySelector("#status").textContent).toBe(""),
    );
    expect(input.disabled).toBe(false);
    expect(
      [...document.querySelectorAll("#messages li")].at(-1).textContent,
    ).toContain("open issues: 1");
  });

  it("does not send an empty message", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1");
    document.querySelector("#turn-input").value = "   ";

    document.querySelector("#composer").dispatchEvent(new document.defaultView.Event("submit", { cancelable: true }));

    expect(postTurn).not.toHaveBeenCalled();
  });

  it("shows the SESSION_LOCKED retry hint without re-sending", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1");
    postTurn.mockResolvedValue({
      ok: false,
      status: 409,
      error: { code: "SESSION_LOCKED", message: "session locked" },
    });
    document.querySelector("#turn-input").value = "hello";

    document.querySelector("#composer").dispatchEvent(new document.defaultView.Event("submit", { cancelable: true }));
    await vi.waitFor(() =>
      expect(document.querySelector("#turn-input").disabled).toBe(false),
    );

    expect(postTurn).toHaveBeenCalledTimes(1);
    expect(document.querySelector("#status").textContent).toContain(
      "another request holds the turn lease",
    );
  });
});

describe("increment 3 — parked, accepted, completed, finalizing", () => {
  beforeEach(() => {
    globalThis.confirm ??= () => true;
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
  });

  it("active session shows the accept control; accepting sends a po_accepted turn and renders report links", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1", { onRestartStory() {} });
    expect(document.querySelector("#accept-turn").hidden).toBe(false);

    postTurn.mockResolvedValue(
      ok({
        session_id: "s-1",
        turn_number: 4,
        outcome: "finalize",
        state: "completed",
        facilitator_reply: null,
        issues: [],
        report: [reportDownload("md"), reportDownload("pdf")],
      }),
    );

    document.querySelector("#accept-turn").click();
    await vi.waitFor(() =>
      expect(document.querySelectorAll("#report-links a").length).toBe(2),
    );

    expect(postTurn).toHaveBeenCalledWith("s-1", { message: undefined, poAccepted: true });
    const [mdLink, pdfLink] = [...document.querySelectorAll("#report-links a")];
    expect(mdLink.href).toContain("report.md");
    expect(pdfLink.href).toContain("report.pdf");
    expect(document.querySelector("#turn-input").disabled).toBe(true);
    expect(document.querySelector("#accept-turn").hidden).toBe(true);
  });

  it("does not send an acceptance turn when the confirm dialog is dismissed", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1", { onRestartStory() {} });
    vi.spyOn(globalThis, "confirm").mockReturnValue(false);

    document.querySelector("#accept-turn").click();

    expect(postTurn).not.toHaveBeenCalled();
  });

  it("parked session offers starting a new session on the same story", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()], "parked")));
    const onRestartStory = vi.fn();
    await openSession("s-1", { onRestartStory });

    const restart = document.querySelector("#restart-story");
    expect(restart).not.toBeNull();
    restart.click();
    expect(onRestartStory).toHaveBeenCalledWith("story-04");
  });

  it("completed session renders persisted report links and regenerates them on demand", async () => {
    fetchSession.mockResolvedValue(
      ok({ ...sessionDetail([turn()], "completed"), reports: [reportDownload("md")] }),
    );
    await openSession("s-1", { onRestartStory() {} });

    expect(document.querySelector("#report-links a").href).toContain("report.md");

    fetchReport.mockResolvedValue(
      ok({ session_id: "s-1", report: [reportDownload("md"), reportDownload("pdf")] }),
    );
    document.querySelector("#regenerate-report").click();
    await vi.waitFor(() =>
      expect(document.querySelectorAll("#report-links a").length).toBe(2),
    );
    expect(fetchReport).toHaveBeenCalledWith("s-1");
  });

  it("finalizing session surfaces the finalize-retry control", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()], "finalizing")));
    await openSession("s-1", { onRestartStory() {} });

    finalizeRetry.mockResolvedValue(
      ok({ session_id: "s-1", report: [reportDownload("md")] }),
    );
    document.querySelector("#retry-finalize").click();
    await vi.waitFor(() =>
      expect(document.querySelector("#report-links a").href).toContain("report.md"),
    );
    expect(finalizeRetry).toHaveBeenCalledWith("s-1");
  });
});
