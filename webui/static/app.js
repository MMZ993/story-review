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

import { createSession, fetchStories, fetchStoryDetail } from "./api.js";
import { openSession } from "./chat.js";
import { renderMarkdown } from "./markdown.js";

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
 * stories endpoint (increment-0 behavior, kept).
 */
async function showOrchestrationStatus() {
  const result = await fetchStories();
  statusElement.textContent = result.ok
    ? "orchestration: reachable"
    : `orchestration: error (${result.status})`;
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
  renderMarkdown(body, detail.description ?? "", true);
  preview.replaceChildren(heading, body);
}

/**
 * Confirm-button handler: create the session on the selected story.
 * Disables the picker for the duration (one in-flight request), shows the
 * "reviewing…" spinner, persists the session id on success. A 409 means
 * the story already has an active session — surfaced with a hint instead
 * of any automatic retry.
 */
async function startSession() {
  const selected = pickerView.querySelector("input[name=story]:checked");
  const storyId = selected?.value ?? selectedStoryId;
  if (!storyId) return;
  const confirmButton = pickerView.querySelector("#confirm-story");
  confirmButton.disabled = true;
  setSpinner(`reviewing ${storyId}… (this can take up to 5 minutes)`);

  const result = await createSession(storyId);

  if (result.ok) {
    globalThis.localStorage.setItem("session:id", result.body.session_id);
    await openSession(result.body.session_id, { onRestartStory: restartStory });
    return;
  }

  setSpinner(null);
  confirmButton.disabled = false;
  const activeHint =
    result.status === 409 && result.error?.code === "STORY_SESSION_ACTIVE"
      ? " (this story already has an active session — finish it before starting a new one)"
      : "";
  // Errors stay in the picker's visible status line (the session-view
  // #status element is hidden while the picker is shown).
  setSpinner(`${describeError(result)}${activeHint}`);
}

/** Show or clear the picker's spinner/status line. */
function setSpinner(text) {
  document.querySelector("#picker-status").textContent = text ?? "";
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

/**
 * Load the browsing view: story list, filter input wiring, confirm button.
 */
async function showPicker() {
  pickerView.hidden = false;
  const result = await fetchStories();
  if (!result.ok) {
    document.querySelector("#picker-status").textContent =
      describeError(result);
    return;
  }

  allStories = result.body.stories ?? [];
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
    });
    if (resumed) return;
  }
  showPicker();
}

showOrchestrationStatus();
boot();
