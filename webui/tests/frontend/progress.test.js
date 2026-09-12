/**
 * Behavior tests for the live-stage polling loop (static/progress.js):
 * a null stage before any observed stage must NOT end the loop (the
 * server reports null for the first moments of a request — lease, claim,
 * input assembly precede the first stage write); a null after a stage,
 * or a bounded run of nulls, ends it.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../static/api.js", () => ({
  fetchSession: vi.fn(),
}));

import { fetchSession } from "../../static/api.js";
import { pollProcessingStage, setStagePollInterval, stageText } from "../../static/progress.js";

const detail = (processing_stage) => ({ ok: true, status: 200, body: { processing_stage } });

function flush() {
  return new Promise((resolve) => globalThis.setTimeout(resolve, 0));
}

beforeEach(() => {
  vi.resetAllMocks();
  setStagePollInterval(1);
});

describe("stageText", () => {
  it("labels every known stage and falls back for null/unknown", () => {
    expect(stageText("facilitator")).toContain("facilitator is drafting the turn");
    expect(stageText("reviewing")).toContain("reviewers are reviewing");
    expect(stageText(null)).toContain("processing…");
    expect(stageText("nonsense")).toContain("processing…");
  });
});

describe("pollProcessingStage", () => {
  it("survives a leading null stage and reports the stage once it appears", async () => {
    fetchSession
      .mockResolvedValueOnce(detail(null)) // race: server has not set the stage yet
      .mockResolvedValueOnce(detail(null))
      .mockResolvedValue(detail("synthesizing"));
    const onStage = vi.fn();
    const onDone = vi.fn();

    pollProcessingStage("s-1", { onStage, onDone });
    await vi.waitFor(() => expect(onStage).toHaveBeenCalled());
    expect(onDone).not.toHaveBeenCalled();
    expect(onStage).toHaveBeenLastCalledWith(
      expect.objectContaining({ processing_stage: "synthesizing" }),
    );
  });

  it("ends itself once a previously observed stage clears", async () => {
    fetchSession.mockResolvedValueOnce(detail("facilitator")).mockResolvedValue(detail(null));
    const onStage = vi.fn();
    const onDone = vi.fn();

    const stop = pollProcessingStage("s-1", { onStage, onDone });
    await vi.waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    stop();
    expect(onStage).toHaveBeenCalledTimes(1);
  });

  it("ends itself after a bounded run of never-stage nulls", async () => {
    fetchSession.mockResolvedValue(detail(null));
    const onStage = vi.fn();
    const onDone = vi.fn();

    const stop = pollProcessingStage("s-1", { onStage, onDone });
    await vi.waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    stop();
    expect(onStage).not.toHaveBeenCalled();
    expect(fetchSession.mock.calls.length).toBeLessThanOrEqual(3);
  });
});
