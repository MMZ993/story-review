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
  getPendingTurn: vi.fn(),
  clearPendingTurn: vi.fn(),
}));

import { openSession } from "../../static/chat.js";
import { setStagePollInterval } from "../../static/progress.js";
import {
  clearPendingTurn,
  fetchReport,
  fetchSession,
  finalizeRetry,
  getPendingTurn,
  postTurn,
} from "../../static/api.js";

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
  vi.resetAllMocks();
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

  it("offers choosing another story in every state and fires onLeaveSession", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    const onLeaveSession = vi.fn();
    await openSession("s-1", { onLeaveSession });

    const leave = document.querySelector("#leave-session");
    expect(leave).not.toBeNull();
    globalThis.confirm ??= () => true;
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
    leave.click();
    expect(onLeaveSession).toHaveBeenCalledTimes(1);
  });

  it("requires confirmation before leaving even when no turn is in flight", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    const onLeaveSession = vi.fn();
    await openSession("s-1", { onLeaveSession });

    globalThis.confirm ??= () => false;
    const confirmSpy = vi.spyOn(globalThis, "confirm").mockReturnValue(false);
    document.querySelector("#leave-session").click();
    expect(onLeaveSession).not.toHaveBeenCalled();
    expect(confirmSpy).toHaveBeenCalledTimes(1);

    confirmSpy.mockReturnValue(true);
    document.querySelector("#leave-session").click();
    expect(onLeaveSession).toHaveBeenCalledTimes(1);
  });

  it("leave-session control is also present on a completed session", async () => {
    fetchSession.mockResolvedValue(
      ok({ ...sessionDetail([turn()], "completed"), reports: [reportDownload("md")] }),
    );
    await openSession("s-1", { onLeaveSession() {} });

    expect(document.querySelector("#leave-session")).not.toBeNull();
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

describe("webui debt fixes + live progress (Item F)", () => {
  it("a failed turn removes the optimistic PO bubble and restores the message for editing", async () => {
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1");
    const input = document.querySelector("#turn-input");

    postTurn.mockResolvedValue({
      ok: false,
      status: 503,
      error: { code: "UPSTREAM_UNAVAILABLE", message: "reviewers unreachable" },
    });
    input.value = "please re-check the rate limit";
    document.querySelector("#send-turn").click();
    await vi.waitFor(() =>
      expect(document.querySelector("#status").textContent).toContain(
        "reviewers unreachable",
      ),
    );
    const bubbles = [...document.querySelectorAll("#messages .message-user")];
    expect(bubbles.map((b) => b.textContent)).toEqual([
      "the API limit is 100 rps", // history only — optimistic bubble gone
    ]);
    expect(input.value).toBe("please re-check the rate limit");
    expect(input.disabled).toBe(false);
  });

  it("opening a session clears a stale status line from a previous session", async () => {
    document.querySelector("#status").textContent = "old error from another session";
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1");
    expect(document.querySelector("#status").textContent).toBe("");
  });

  it("resumes a pending turn after a mid-turn reload by re-issuing it with the stored body", async () => {
    getPendingTurn.mockReturnValue({ message: "mid-flight message", poAccepted: false });
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));

    let resolveTurn;
    postTurn.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveTurn = resolve;
        }),
    );
    const opening = openSession("s-1"); // awaits the resumed turn inside

    await vi.waitFor(() => expect(postTurn).toHaveBeenCalled());
    expect(postTurn).toHaveBeenCalledWith(
      "s-1",
      { message: "mid-flight message", poAccepted: false },
    );
    expect(document.querySelector("#turn-input").disabled).toBe(true);
    const bubbles = [...document.querySelectorAll("#messages .message-user")];
    expect(bubbles.at(-1).textContent).toBe("mid-flight message");

    resolveTurn(
      ok({
        session_id: "s-1",
        turn_number: 3,
        outcome: "continue",
        state: "active",
        facilitator_reply: "resumed reply",
        issues: ["limit"],
      }),
    );
    await opening;
    expect([...document.querySelectorAll("#messages li")].at(-1).textContent).toContain(
      "open issues: 1",
    );
    expect(getPendingTurn).toHaveBeenCalledWith("s-1");
    expect(document.querySelector("#turn-input").disabled).toBe(false);
  });

  it("shows live stage placeholders while a turn is processing and removes them on completion", async () => {
    setStagePollInterval(10);
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await openSession("s-1");
    const input = document.querySelector("#turn-input");

    let resolveTurn;
    postTurn.mockReturnValue(
      new Promise((resolve) => {
        resolveTurn = resolve;
      }),
    );
    // arm the staged mock BEFORE the click: the poll's first read is immediate
    fetchSession.mockResolvedValue(
      ok({ ...sessionDetail([turn()]), processing_stage: "facilitator" }),
    );
    input.value = "status?";
    document.querySelector("#send-turn").click();

    // first poll observes the facilitator stage
    await vi.waitFor(() => {
      const placeholder = document.querySelector(".message-progress");
      expect(placeholder?.textContent).toContain("facilitator is drafting the turn");
    });

    // stage advances to delegated re-review
    fetchSession.mockResolvedValue(
      ok({ ...sessionDetail([turn()]), processing_stage: "delegating" }),
    );
    await vi.waitFor(() => {
      const placeholder = document.querySelector(".message-progress");
      expect(placeholder?.textContent).toContain("reviewers are re-checking");
    });

    resolveTurn(
      ok({
        session_id: "s-1",
        turn_number: 3,
        outcome: "continue",
        state: "active",
        facilitator_reply: "done",
        issues: [],
      }),
    );
    await vi.waitFor(() =>
      expect(document.querySelector(".message-progress")).toBeNull(),
    );
  });
});

describe("passive processing view (another client / creation in flight)", () => {
  it("clears the placeholder and re-enables the composer when the stage clears", async () => {
    const { setStagePollInterval } = await import("../../static/progress.js");
    setStagePollInterval(10);
    fetchSession.mockResolvedValue(
      ok({ ...sessionDetail([turn()]), processing_stage: "reviewing" }),
    );
    await openSession("s-1");

    // passive mode: composer locked, placeholder shows the stage
    expect(document.querySelector("#turn-input").disabled).toBe(true);
    expect(document.querySelector(".message-progress")?.textContent).toContain(
      "reviewers are reviewing the story",
    );

    // stage clears -> placeholder removed, history re-rendered, composer back
    fetchSession.mockResolvedValue(ok(sessionDetail([turn()])));
    await vi.waitFor(() =>
      expect(document.querySelector(".message-progress")).toBeNull(),
    );
    await vi.waitFor(() =>
      expect(document.querySelector("#turn-input").disabled).toBe(false),
    );
    expect(document.querySelectorAll("#messages .message-user").length).toBe(1);
  });

  it("stops the passive poll when leaving via choose another story", async () => {
    const onLeaveSession = vi.fn();
    fetchSession.mockResolvedValue(
      ok({ ...sessionDetail([turn()]), processing_stage: "synthesizing" }),
    );
    await openSession("s-1", { onLeaveSession });
    globalThis.confirm ??= () => true;
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
    document.querySelector("#leave-session").click();
    expect(onLeaveSession).toHaveBeenCalledTimes(1);
    // the poll was stopped: no further fetches fire after leaving
    const callsAfterLeave = fetchSession.mock.calls.length;
    await new Promise((resolve) => globalThis.setTimeout(resolve, 40));
    expect(fetchSession.mock.calls.length).toBe(callsAfterLeave);
  });
});

describe("report-links hygiene", () => {
  it("clears report links left by a previous completed session when opening an active one", async () => {
    const links = document.querySelector("#report-links");
    const stale = document.createElement("a");
    stale.href = "https://127.0.0.1:9026/old/report.md";
    links.append(stale);

    fetchSession.mockResolvedValue(ok(sessionDetail([turn()]))); // active
    await openSession("s-1");

    expect(links.children.length).toBe(0);
  });
});
