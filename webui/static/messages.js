/**
 * Chat message rendering (shared by history replay and live turns).
 *
 * Pure DOM construction for the message list: PO bubbles are plain text
 * (PO input is never markdown-rendered), facilitator bubbles render
 * sanitized markdown (raw HTML/images stripped by the shared renderer)
 * plus a meta line with the open-issue count, synthesis reference and
 * turn outcome. No fetching, no state — the view controller (chat.js)
 * owns those.
 */

import { renderMarkdown } from "./markdown.js";

/** One chat bubble: `side` "user" (PO, right) or "assistant" (left). */
function bubble(side, contentNode) {
  const li = document.createElement("li");
  li.className = `message-${side}`;
  li.append(contentNode);
  return li;
}

/** Append a PO message bubble; returns it. */
export function appendPoMessage(list, text) {
  const li = bubble("user", document.createTextNode(text));
  list.append(li);
  scrollList(list);
  return li;
}

/**
 * Append a facilitator reply: markdown body + meta line
 * ("turn N — open issues: k · synthesis: art-… vN · outcome: …").
 */
export function appendFacilitatorTurn(list, reply, meta) {
  const body = document.createElement("div");
  renderMarkdown(body, reply ?? "", true);

  const parts = [];
  if (Array.isArray(meta.issues)) parts.push(`open issues: ${meta.issues.length}`);
  if (meta.synthesis?.artifact_id) {
    parts.push(`synthesis: ${meta.synthesis.artifact_id} v${meta.synthesis.version}`);
  }
  if (meta.outcome) parts.push(`outcome: ${meta.outcome}`);
  const metaLine = document.createElement("div");
  metaLine.className = "message-meta";
  metaLine.textContent = `turn ${meta.turnNumber}${parts.length ? ` — ${parts.join(" · ")}` : ""}`;

  const bodyBubble = bubble("assistant", body);
  const metaBubble = bubble("assistant", metaLine);
  list.append(bodyBubble, metaBubble);
  scrollList(list);
  return [bodyBubble, metaBubble];
}

/** Keep the newest message visible. */
function scrollList(list) {
  list.scrollTop = list.scrollHeight;
}

/**
 * Ephemeral processing placeholder (Item F): an assistant-side bubble
 * that shows the server's current pipeline stage and is removed when the
 * real response arrives — never persisted, never part of history replay.
 */
export function appendProgress(list) {
  const li = bubble("assistant", document.createTextNode(""));
  li.classList.add("message-progress");
  list.append(li);
  scrollList(list);
  return {
    update(text) {
      li.textContent = text;
      scrollList(list);
    },
    remove() {
      li.remove();
    },
  };
}

/**
 * Replace the message list with the full turn history (TurnView list from
 * SessionDetail): PO messages, acceptance actions ("(accepted the
 * report)"), and facilitator replies in chronological order.
 */
export function renderHistory(list, turns) {
  list.replaceChildren();
  for (const turn of turns) {
    if (turn.po_message) appendPoMessage(list, turn.po_message);
    if (turn.po_accepted) appendPoMessage(list, "(accepted the report)");
    if (turn.facilitator_reply) {
      appendFacilitatorTurn(list, turn.facilitator_reply, {
        issues: turn.delegation?.open_issues,
        synthesis: (turn.produced_artifacts ?? []).find(
          (ref) => ref.type === "synthesis",
        ),
        outcome: turn.outcome,
        turnNumber: turn.turn_number,
      });
    }
  }
  scrollList(list);
}
