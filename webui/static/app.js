/**
 * Increment-0 app shell: verify same-origin proxy reachability of the
 * orchestration service and surface it in the header. Probes the real
 * stories endpoint (orchestration's /health lives outside the /api prefix
 * the proxy forwards). Conversation logic (state machine, story picker,
 * turns) arrives in increments 1-3.
 *
 * Side effects: one fetch of /api/v1/stories on load; writes text to the
 * #orchestration-status element.
 */

const statusElement = document.querySelector("#orchestration-status");

async function showOrchestrationStatus() {
  try {
    const response = await fetch("/api/v1/stories?limit=1");
    statusElement.textContent = response.ok
      ? "orchestration: reachable"
      : `orchestration: error (${response.status})`;
  } catch {
    statusElement.textContent = "orchestration: unreachable";
  }
}

showOrchestrationStatus();
