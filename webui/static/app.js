/**
 * Increment-1 app shell: story picker + session creation.
 *
 * State machine (api-contract "Client interaction states"): browsing →
 * (confirm story) → POST /sessions with a persisted Idempotency-Key
 * ("reviewing…" spinner, up to 5 min server-side) → session created
 * (chat view arrives in increment 2). Error envelopes from the API client
 * are surfaced as text; 409 SESSION_ACTIVE gets a dedicated hint.
 *
 * Picker layout: header controls, a foldable filtered story list, then a
 * full-width detail preview. The filter narrows the loaded list client-side
 * (dataset is bounded, no pagination). Preview content renders through the
 * shared markdown renderer (sanitized, raw HTML stripped).
 *
 * Side effects: DOM writes to #picker-view / #session-view / #story-preview
 * and localStorage (via the api client for idempotency keys, plus the
 * created session id under "session:id" for increment-2 resume).
 */

import { createSession, fetchSessions, fetchStories, fetchStoryDetail } from "./api.js";
import { openSession } from "./chat.js";
import { renderStoryPreview } from "./markdown.js";
import { stageText } from "./progress.js";
import { renderOpenSessions, renderPastSessions } from "./sessions-list.js";

const statusElement = document.querySelector("#orchestration-status");
const pickerView = document.querySelector("#picker-view");

/** All stories from the initial GET /stories (filtering is client-side). */
let allStories = [];

/** Cache of story details already fetched for the hover preview. */
const detailCache = new Map();

/** Selected story id, retained while a filter temporarily hides its row. */
let selectedStoryId = null;

/**
 * Report the orchestration reachability in the header by probing the real
 * stories endpoint (increment-0 behavior, kept). The data-status attribute
 * lets the presentation distinguish a reachable service from an error.
 */
async function showOrchestrationStatus() {
  const result = await fetchStories();
  statusElement.dataset.status = result.ok ? "reachable" : "error";
  statusElement.textContent = result.ok
    ? "FastAPI backend: reachable"
    : `FastAPI backend: error (${result.status})`;
}

/**
 * Human-readable text for an API client failure: the error envelope's
 * message when present, otherwise a generic status line.
 */
function describeError(result) {
  return result.error?.message ?? `request failed (${result.status})`;
}

/**
 * Case-insensitive substring filter over story titles; an empty query
 * returns the full list.
 */
function filterStories(stories, query) {
  if (!query) return stories;
  const needle = query.toLowerCase();
  return stories.filter((story) =>
    (story.title ?? story.story_id).toLowerCase().includes(needle),
  );
}

/**
 * Render one story as a picker row (radio input + label). Selection is
 * confirmable; hover/focus loads the detail preview.
 */
function renderStoryRow(story, listElement) {
  const li = document.createElement("li");
  li.className = "story-row";

  const input = document.createElement("input");
  input.type = "radio";
  input.name = "story";
  input.id = `story-${story.story_id}`;
  input.value = story.story_id;

  const label = document.createElement("label");
  label.htmlFor = input.id;
  label.textContent = story.title ?? story.story_id;

  input.addEventListener("focus", () => showPreview(story.story_id));
  input.addEventListener("change", () => {
    selectedStoryId = input.value;
    updateStorySummary();
  });
  label.addEventListener("mouseenter", () => showPreview(story.story_id));

  li.append(input, label);
  listElement.append(li);
}

/** Render the (filtered) story list, keeping the current selection. */
function renderStoryList() {
  const listElement = pickerView.querySelector("#story-list");
  const selected = pickerView.querySelector("input[name=story]:checked");
  const selectedId = selected?.value ?? selectedStoryId;
  const query = pickerView.querySelector("#story-filter").value.trim();

  listElement.replaceChildren();
  const visible = filterStories(allStories, query);
  if (visible.length === 0) {
    const li = document.createElement("li");
    li.className = "story-empty";
    li.textContent = "no stories match the filter";
    listElement.append(li);
    updateStorySummary();
    return;
  }
  for (const story of visible) renderStoryRow(story, listElement);

  if (selectedId) {
    const restored = listElement.querySelector(`#story-${selectedId}`);
    if (restored) restored.checked = true;
  }
  updateStorySummary();
}

/** Render the story count and selected title in the collapsed picker summary. */
function updateStorySummary() {
  const summary = pickerView.querySelector("#story-summary");
  const selected = pickerView.querySelector("input[name=story]:checked");
  const storyId = selected?.value ?? selectedStoryId;
  const story = allStories.find((item) => item.story_id === storyId);
  const title = story?.title ?? story?.story_id;
  summary.textContent = `stories (${allStories.length})${title ? ` — selected: ${title}` : ""}`;
}

/**
 * Load the story detail for the hover/focus preview (cached) and render it
 * as sanitized markdown — the renderer strips raw HTML and images.
 */
async function showPreview(storyId) {
  const preview = pickerView.querySelector("#story-preview");
  if (!preview) return;
  preview.replaceChildren(document.createTextNode("loading…"));

  let detail = detailCache.get(storyId);
  if (!detail) {
    const result = await fetchStoryDetail(storyId);
    if (!result.ok) {
      preview.replaceChildren(document.createTextNode(describeError(result)));
      return;
    }
    detail = result.body;
    detailCache.set(storyId, detail);
  }

  const heading = document.createElement("h3");
  heading.textContent = detail.title ?? storyId;
  const body = document.createElement("div");
  renderStoryPreview(body, detail.description ?? "");
  preview.replaceChildren(heading, body);
}

/**
 * Confirm-button handler: create the session on the selected story.
 * Disables the picker for the duration (one in-flight request), shows the
 * "reviewing…" spinner, persists the session id on success. While the
 * synchronous POST is outstanding, the session list is polled for the
 * story's *processing* session (one active session per story; only the
 * processing one carries a stage) — once discovered, the session view
 * opens early and shows live stage placeholders (Item F), replaced by the
 * real opening turn when the POST completes. A 409 means the story
 * already has an active session — surfaced with a hint instead of any
 * automatic retry.
 */
async function startSession() {
  const selected = pickerView.querySelector("input[name=story]:checked");
  const storyId = selected?.value ?? selectedStoryId;
  if (!storyId) return;
  const confirmButton = pickerView.querySelector("#confirm-story");
  confirmButton.disabled = true;
  setSpinner(`reviewing ${storyId}… (this can take up to 5 minutes)`);
  const stopProgressPolling = pollCreationProgress(storyId);

  const result = await createSession(storyId);
  stopProgressPolling();

  if (result.ok) {
    globalThis.localStorage.setItem("session:id", result.body.session_id);
    setSpinner(null);
    await openSession(result.body.session_id, {
      onRestartStory: restartStory,
      onLeaveSession: leaveSession,
    });
    return;
  }

  setSpinner(null);
  confirmButton.disabled = false;
  const activeHint =
    result.status === 409 && result.error?.code === "STORY_SESSION_ACTIVE"
      ? " (this story already has an active session — resume it from the open sessions list)"
      : "";
  // Errors stay in the picker's visible status line (the session-view
  // #status element is hidden while the picker is shown); if the progress
  // poll already switched to the session view, surface it there instead.
  const message = `${describeError(result)}${activeHint}`;
  setSpinner(message);
  if (!document.querySelector("#session-view").hidden) {
    document.querySelector("#status").textContent = message;
  }
}

/**
 * Poll GET /sessions while a creation POST is outstanding; once the
 * story's processing session appears, open the session view early — its
 * passive processing mode (chat.js) renders the live stage placeholder
 * from the polled detail. Returns a stop() handle.
 */
function pollCreationProgress(storyId) {
  const timer = globalThis.setInterval(async () => {
    const result = await fetchSessions();
    if (!result.ok) return;
    const processing = (result.body.sessions ?? []).find(
      (session) =>
        session.story_id === storyId &&
        session.state === "active" &&
        session.processing_stage,
    );
    if (!processing) return;
    globalThis.clearInterval(timer);
    setSpinner(`reviewing ${storyId}… — ${stageText(processing.processing_stage)}`);
    await openSession(processing.session_id, {
      onRestartStory: restartStory,
      onLeaveSession: leaveSession,
    });
  }, 4000);
  return () => globalThis.clearInterval(timer);
}

/** Show or clear the picker's spinner/status line. */
function setSpinner(text) {
  document.querySelector("#picker-status").textContent = text ?? "";
}

/**
 * Leave the session view: drop the stored session id and return to the
 * picker with no preselection (the session stays resumable server-side;
 * re-entering requires the session id — e.g. via the API).
 */
function leaveSession() {
  globalThis.localStorage.removeItem("session:id");
  document.querySelector("#session-view").hidden = true;
  selectedStoryId = null;
  showPicker();
}

/**
 * Parked-session restart: drop the stored session id and return to the
 * picker with the same story preselected, ready for a fresh POST /sessions.
 */
function restartStory(storyId) {
  globalThis.localStorage.removeItem("session:id");
  document.querySelector("#session-view").hidden = true;
  selectedStoryId = storyId;
  showPicker();
}

/** Resume a listed open session: store its id and open the session view. */
async function resumeSession(sessionId) {
  globalThis.localStorage.setItem("session:id", sessionId);
  await openSession(sessionId, {
    onRestartStory: restartStory,
    onLeaveSession: leaveSession,
  });
}

/**
 * Load the browsing view: open-sessions list (resume path for active
 * sessions), story list, filter input wiring, confirm button. The confirm
 * button is re-enabled here — a successful creation disables it and only
 * the error path re-enables it, so returning to the picker must reset it.
 */
async function showPicker() {
  pickerView.hidden = false;
  pickerView.querySelector("#confirm-story").disabled = false;
  const [storiesResult, sessionsResult] = await Promise.all([fetchStories(), fetchSessions()]);
  if (!storiesResult.ok) {
    document.querySelector("#picker-status").textContent =
      describeError(storiesResult);
    return;
  }

  allStories = storiesResult.body.stories ?? [];
  renderOpenSessions(
    pickerView.querySelector("#open-sessions-list"),
    pickerView.querySelector("#open-sessions-summary"),
    sessionsResult.ok ? sessionsResult.body.sessions : null,
    allStories,
    resumeSession,
  );
  renderPastSessions(
    pickerView.querySelector("#past-sessions-list"),
    pickerView.querySelector("#past-sessions-summary"),
    sessionsResult.ok ? sessionsResult.body.sessions : null,
    allStories,
    resumeSession,
  );
  // Wire once: showPicker runs again on parked-session restart.
  const picker = pickerView.querySelector("#story-picker");
  if (!picker.dataset.wired) {
    pickerView
      .querySelector("#story-filter")
      .addEventListener("input", renderStoryList);
    pickerView
      .querySelector("#confirm-story")
      .addEventListener("click", startSession);
    picker.dataset.wired = "true";
  }
  renderStoryList();
  if (selectedStoryId) showPreview(selectedStoryId);
}

/**
 * Boot: resume the stored session when one is active (client rule: hold
 * the session id; every turn resumes server-side) — history replays from
 * GET /sessions/{id}; a stale id (404) clears the key and falls back to
 * the picker.
 */
async function boot() {
  const storedId = globalThis.localStorage.getItem("session:id");
  if (storedId) {
    const resumed = await openSession(storedId, {
      onUnknownSession() {
        globalThis.localStorage.removeItem("session:id");
      },
      onRestartStory: restartStory,
      onLeaveSession: leaveSession,
    });
    if (resumed) return;
  }
  showPicker();
}

showOrchestrationStatus();
boot();
