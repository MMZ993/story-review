/**
 * Live processing-stage progress (future-extensions Item F, option a).
 *
 * The server publishes its current pipeline position on the session
 * (`processing_stage`, advisory — schemas.md); this module maps stages to
 * human-readable placeholder text and provides the polling loop that
 * keeps a placeholder bubble in the chat current while a synchronous
 * POST /sessions or POST /turns is outstanding. Polling stops as soon as
 * the stage clears (the flow finished) and never on its own makes
 * correctness decisions — the POST response remains the sole authority.
 */

import { fetchSession } from "./api.js";

/** One human sentence per server stage (schemas.md ProcessingStage). */
const STAGE_LABELS = {
  reviewing: "business + engineering reviewers are reviewing the story…",
  synthesizing: "synthesis agent is merging both perspectives…",
  facilitator: "facilitator is drafting the turn…",
  delegating: "reviewers are re-checking the delegated concerns…",
  finalizing: "rendering the final report…",
};

/** Label for a stage; unknown/null falls back to a neutral line. */
export function stageText(stage) {
  return STAGE_LABELS[stage] ?? "processing… (this can take several minutes)";
}

/** Default detail-poll cadence; overridable for tests. */
let pollIntervalMs = 4000;

export function setStagePollInterval(ms) {
  /* also mirrored by chat.js tests via direct import */
  pollIntervalMs = ms;
}

/**
 * Poll GET /sessions/{id} and invoke `onStage(detail)` for each
 * successful read while the session reports a non-null processing stage.
 * The first read happens immediately (the POST just fired). A null stage
 * is only treated as "done" once a non-null stage was observed before —
 * the server legitimately reports null for the first moments of a request
 * (lease → claim → input assembly precede the first stage write), and an
 * eager stop there would freeze the placeholder at its generic text. A
 * never followed a stage keeps polling (bounded: a run of nulls without
 *   any observed stage also ends the loop — the flow may have finished
 *   between the arming read and the first poll). Returns a
 * `stop()` that ends the loop; the loop also ends by itself once a read
 * observes a cleared stage (calls `onDone()` once in that case).
 */
export function pollProcessingStage(sessionId, { onStage, onDone = () => {} } = {}) {
  const NULL_RUN_LIMIT = 3;
  let stopped = false;
  let timer = null;
  let sawStage = false;
  let nullRun = 0;

  async function tick() {
    if (stopped) return;
    const result = await fetchSession(sessionId);
    if (stopped) return;
    if (result.ok) {
      if (result.body.processing_stage) {
        sawStage = true;
        nullRun = 0;
        onStage(result.body);
      } else {
        nullRun += 1;
        if (sawStage || nullRun >= NULL_RUN_LIMIT) {
          stopped = true;
          onDone(result.body);
          return;
        }
      }
    }
    if (!stopped) timer = globalThis.setTimeout(tick, pollIntervalMs);
  }

  tick();
  return () => {
    stopped = true;
    if (timer !== null) globalThis.clearTimeout(timer);
  };
}
