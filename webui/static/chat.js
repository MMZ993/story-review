/**
 * Session chat view controller (increments 2–3).
 *
 * Owns the session-view state machine: active (composer + accept control,
 * exactly one in-flight logical request), parked (read-only history +
 * restart-on-same-story), finalizing (finalize-retry control), completed
 * (read-only history + report links with on-demand signed-URL
 * regeneration). History replay comes from GET /sessions/{id} — the server
 * is the sole source of truth after any reload.
 *
 * Side effects: DOM writes inside #session-view; all fetching goes through
 * the api client (which owns idempotency-key persistence).
 */

import {
  clearPendingTurn,
  fetchReport,
  fetchSession,
  finalizeRetry,
  getPendingTurn,
  postTurn,
} from "./api.js";
import { appendFacilitatorTurn, appendPoMessage, appendProgress, renderHistory } from "./messages.js";
import { pollProcessingStage, stageText } from "./progress.js";

const MAX_FACILITATOR_TURNS = 10;

/** Session state driving the controls: only "active" accepts input. */
let sessionState = "active";

let sessionId = null;
let storyId = null;
let inFlight = false;

/** Stop handle of the passive stage poll (openSession processing view). */
let stagePollStop = null;

/** Host callbacks (app.js): stale-id fallback, parked-session restart,
 * and leave-session (back to the picker). */
let onUnknownSession = null;
let onRestartStory = null;
let onLeaveSession = null;

/**
 * Human-readable text for an API client failure: the error envelope's
 * message when present, otherwise a generic status line.
 */
function describeError(result) {
  return result.error?.message ?? `request failed (${result.status})`;
}

/** Show or clear the session status line (spinner/hints). */
function setStatus(text) {
  document.querySelector("#status").textContent = text ?? "";
}

/** Session header line: story, state, facilitator-turn budget. */
function renderHeader(detail) {
  document.querySelector("#session-header").textContent =
    `${detail.story_id} — ${detail.state}` +
    ` — facilitator turns ${detail.facilitator_turn_count}/${MAX_FACILITATOR_TURNS}` +
    ` (${detail.session_id})`;
}

/** Refresh the header from the server (turn budget after a turn). */
async function refreshHeader() {
  const result = await fetchSession(sessionId);
  if (result.ok) renderHeader(result.body);
}

/**
 * Enable/disable the composer and accept control based on the session
 * state; the in-flight guard keeps exactly one logical request running.
 */
function syncComposer() {
  const active = sessionState === "active";
  document.querySelector("#turn-input").disabled = !active || inFlight;
  document.querySelector("#send-turn").disabled = !active || inFlight;
  document.querySelector("#accept-turn").hidden = !active || inFlight;
}

/** Report links: one anchor per rendered format (signed URL as returned). */
function renderReportLinks(reports) {
  const container = document.querySelector("#report-links");
  container.replaceChildren();
  for (const entry of reports ?? []) {
    const link = document.createElement("a");
    link.href = entry.signed_url;
    link.textContent = `download report (.${entry.format})`;
    link.target = "_blank";
    link.rel = "noopener";
    container.append(link);
  }
}

/** One button helper for the #session-actions container. */
function actionButton(id, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.id = id;
  button.textContent = label;
  return button;
}

/**
 * State-specific controls under #session-actions, plus the persistent
 * "choose another story" control (every state — it only drops the stored
 * session id client-side; the session itself stays untouched server-side
 * and resumable by creating a new browser session or via the API):
 * - parked: "start a new session on this story" (host decides the routing);
 * - finalizing: retry POST /finalize (503 render failures stay retryable);
 * - completed: regenerate the signed report URLs (GET /report).
 */
function renderStateControls() {
  const actions = document.querySelector("#session-actions");
  actions.replaceChildren();

  if (sessionState === "parked") {
    setStatus("session parked — read-only");
    const restart = actionButton("restart-story", "start a new session on this story");
    restart.addEventListener("click", () => onRestartStory?.(storyId));
    actions.append(restart);
  } else if (sessionState === "finalizing") {
    setStatus("session is finalizing — retry if it does not complete");
    const retry = actionButton("retry-finalize", "retry finalize");
    retry.addEventListener("click", runFinalizeRetry);
    actions.append(retry);
  } else if (sessionState === "completed") {
    setStatus("session completed — read-only");
    const regenerate = actionButton("regenerate-report", "regenerate report links");
    regenerate.addEventListener("click", regenerateReportLinks);
    actions.append(regenerate);
  }
  const leave = actionButton("leave-session", "choose another story");
  leave.addEventListener("click", () => {
    if (inFlight && !globalThis.confirm?.("A turn is still processing — leave anyway? (it keeps running server-side)")) {
      return;
    }
    if (stagePollStop) {
      stagePollStop();
      stagePollStop = null;
    }
    onLeaveSession?.();
  });
  actions.append(leave);
}

/** POST /finalize retry: completes a finalizing session with report links. */
async function runFinalizeRetry() {
  setStatus("finalizing… (rendering the report)");
  const result = await finalizeRetry(sessionId);
  if (result.ok) {
    sessionState = "completed";
    setStatus(null);
    renderReportLinks(result.body.report);
    renderStateControls();
    refreshHeader();
  } else {
    setStatus(describeError(result));
  }
}

/** GET /report: fresh signed URLs for a completed session. */
async function regenerateReportLinks() {
  setStatus("regenerating report links…");
  const result = await fetchReport(sessionId);
  if (result.ok) {
    setStatus(null);
    renderReportLinks(result.body.report);
  } else {
    setStatus(describeError(result));
  }
}

/**
 * Composer submit: exactly one in-flight logical turn. The PO message is
 * rendered immediately (optimistic), then POST /turns runs with its own
 * idempotency key (persisted by the api client). 409 SESSION_LOCKED gets
 * the contract's retry hint (a NEW request after the lease expires).
 */
async function sendTurn(event) {
  event.preventDefault();
  if (inFlight) return;
  const input = document.querySelector("#turn-input");
  const message = input.value.trim();
  if (!message) return;
  await runTurn(() => postTurn(sessionId, { message }), message, { restoreToInput: true });
  input.focus();
}

/**
 * Accept-and-finalize button: explicit client action (guarded by a confirm
 * dialog — acceptance bypasses the facilitator and completes the session).
 */
async function acceptReport() {
  if (inFlight) return;
  if (!globalThis.confirm?.("Accept the report and finalize this session?")) return;
  await runTurn(() => postTurn(sessionId, { poAccepted: true }), "(accepted the report)");
}

/**
 * Shared single-turn runner: optimistic PO bubble, in-flight guard, live
 * stage placeholder (Item F), facilitator reply + outcome handling, error
 * surfacing. On failure the optimistic bubble is removed and a message
 * turn's text is restored to the composer for editing (webui debt 1).
 */
async function runTurn(post, optimisticPoBubble, { restoreToInput = false } = {}) {
  const input = document.querySelector("#turn-input");
  inFlight = true;
  if (restoreToInput) input.value = "";
  syncComposer();
  const optimistic = appendPoMessage(document.querySelector("#messages"), optimisticPoBubble);
  const placeholder = appendProgress(document.querySelector("#messages"));
  placeholder.update(stageText(null));
  const stopPolling = pollProcessingStage(sessionId, {
    onStage: (detail) => placeholder.update(stageText(detail.processing_stage)),
  });
  setStatus("processing… (this can take several minutes)");

  const result = await post();

  stopPolling();
  placeholder.remove();
  inFlight = false;
  if (result.ok) {
    setStatus(null);
    sessionState = result.body.state;
    if (result.body.facilitator_reply) {
      appendFacilitatorTurn(document.querySelector("#messages"), result.body.facilitator_reply, {
        issues: result.body.issues,
        synthesis: result.body.synthesis,
        outcome: result.body.outcome,
        turnNumber: result.body.turn_number,
      });
    }
    if (sessionState === "completed") renderReportLinks(result.body.report);
    renderStateControls();
    refreshHeader();
  } else {
    optimistic.remove();
    if (restoreToInput) input.value = optimisticPoBubble;
    const lockedHint =
      result.status === 409 && result.error?.code === "SESSION_LOCKED"
        ? " (another request holds the turn lease — wait for it to finish or expire, then send a new message)"
        : "";
    setStatus(`${describeError(result)}${lockedHint}`);
  }
  syncComposer();
}

/**
 * Open (or resume) the session view: fetch the detail, replay history,
 * wire the composer and state controls. `onUnknownSession` fires on 404
 * (stale stored id); `onRestartStory(storyId)` fires when the owner
 * restarts a parked session on the same story; `onLeaveSession()` fires
 * for "choose another story". Returns true when the
 * session view was opened.
 */
export async function openSession(id, handlers = {}) {
  const result = await fetchSession(id);
  if (!result.ok) {
    if (result.status === 404 && handlers.onUnknownSession) handlers.onUnknownSession();
    else setStatus(describeError(result));
    return false;
  }

  onUnknownSession = handlers.onUnknownSession ?? onUnknownSession;
  onRestartStory = handlers.onRestartStory ?? onRestartStory;
  onLeaveSession = handlers.onLeaveSession ?? onLeaveSession;
  sessionId = id;
  storyId = result.body.story_id;
  sessionState = result.body.state;
  inFlight = false; // a freshly opened view is at rest (passive mode re-arms below)

  document.querySelector("#picker-view").hidden = true;
  document.querySelector("#session-view").hidden = false;
  setStatus(null); // never inherit a stale banner from a previous session

  if (stagePollStop) stagePollStop();
  renderHeader(result.body);
  renderHistory(document.querySelector("#messages"), result.body.turns ?? []);
  renderReportLinks(sessionState === "completed" ? (result.body.reports ?? []) : []);
  renderStateControls();
  syncComposer();

  const composer = document.querySelector("#composer");
  if (!composer.dataset.wired) {
    composer.addEventListener("submit", sendTurn);
    document.querySelector("#accept-turn").addEventListener("click", acceptReport);
    composer.dataset.wired = "true";
  }

  const pending = sessionState === "active" ? getPendingTurn(id) : null;
  if (pending) {
    // mid-turn reload (webui debt 3): re-issue the same logical request
    // (the api client reuses the persisted idempotency key → canonical
    // replay server-side) while showing the live stage placeholder.
    await runTurn(
      () =>
        postTurn(sessionId, {
          message: pending.message ?? undefined,
          poAccepted: pending.poAccepted,
        }),
      pending.poAccepted ? "(accepted the report)" : pending.message,
      { restoreToInput: !pending.poAccepted },
    );
  } else if (result.body.processing_stage && sessionState !== "completed") {
    // the server is processing this session (e.g. creation still running
    // or another client's request): read-only view + live placeholder
    inFlight = true;
    syncComposer();
    const placeholder = appendProgress(document.querySelector("#messages"));
    placeholder.update(stageText(result.body.processing_stage));
    stagePollStop = pollProcessingStage(id, {
      onStage: (detail) => placeholder.update(stageText(detail.processing_stage)),
      onDone: () => {
        placeholder.remove();
        stagePollStop = null;
        inFlight = false;
        syncComposer();
        if (sessionId === id) openSession(id); // history replay from truth
      },
    });
  } else {
    clearPendingTurn(id); // drop any legacy key-only residue
  }
  return true;
}
