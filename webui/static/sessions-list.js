/**
 * Open-sessions list for the story picker (increment 4 webui findings).
 *
 * GET /sessions returns every session; this module renders the *active*
 * ones as resumable rows — story title (fallback id), an annotation when
 * the session is currently processing, and a resume button. Resuming is
 * the escape hatch from the one-active-session-per-story 409: instead of
 * a dead-end error, the owner can come back into the existing session.
 * Starting a *new* session on a story with an active one remains blocked
 * server-side by design — the fresh-start path is resume → park →
 * "start a new session on this story" (parked view).
 *
 * Pure DOM rendering: no fetching, no storage — the caller (app.js)
 * supplies the data and the resume callback.
 */

/** Render the active sessions into `listElement` and the count into `summaryElement`. */
export function renderOpenSessions(listElement, summaryElement, sessions, stories, onResume) {
  const open = (sessions ?? []).filter((session) => session.state === "active");
  summaryElement.textContent = `open sessions (${open.length})`;
  listElement.replaceChildren();

  if (open.length === 0) {
    const li = document.createElement("li");
    li.className = "open-sessions-empty";
    li.textContent = "no open sessions";
    listElement.append(li);
    return;
  }

  for (const session of open) {
    const title =
      stories.find((story) => story.story_id === session.story_id)?.title ??
      session.story_id;
    const li = document.createElement("li");
    li.className = "open-session-row";

    const label = document.createElement("span");
    label.textContent =
      `${session.story_id} — ${title}` +
      (session.processing_stage ? ` (processing: ${session.processing_stage})` : "");

    const resume = document.createElement("button");
    resume.type = "button";
    resume.textContent = "resume";
    resume.addEventListener("click", () => onResume(session.session_id));

    li.append(label, resume);
    listElement.append(li);
  }
}
