#!/usr/bin/env bash
# Invoke the disposable Agent Engine caller twice for the connectivity trace.
#
# Tier-1 read/invocation action: sends two Agent Engine requests; the agent
# persists then restores one marker through authenticated Cloud Run MCP. It
# writes no infrastructure configuration, but does consume request-token usage
# and creates the intended disposable database marker. Output is saved locally
# under /tmp for sanitization before recording evidence.
#
# Usage: ./run-agent-trace.sh <agent-engine-id>
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <agent-engine-id>" >&2
  exit 2
fi

cd "$(dirname "$0")"
source ../../infra/envs/home.env
: "${PROJECT_ID:?PROJECT_ID not set in infra/envs/home.env}"
REGION="${REGION:-europe-west4}"
AGENT_ENGINE_ID="$1"
CORRELATION_ID="$(python -c 'import uuid; print(uuid.uuid4().hex)')"
SESSION_ID="spike-${CORRELATION_ID:0:12}"
MARKER="marker-${CORRELATION_ID:12:12}"
TRACE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/spike-trace.XXXXXX")"
ENDPOINT="https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines/${AGENT_ENGINE_ID}:streamQuery?alt=sse"

query() {
  local message="$1"
  curl --fail-with-body --silent --show-error \
    --header "Authorization: Bearer $(gcloud auth print-access-token)" \
    --header "Content-Type: application/json" \
    --request POST "$ENDPOINT" \
    --data "$(jq -nc --arg message "$1" '{classMethod: "async_stream_query", input: {user_id: "connectivity-spike", message: $message}}')"
}

# The streamQuery endpoint (with alt=sse) returns concatenated JSON documents
# (one per event), not SSE-framed text; jq processes them natively.
assert_persist_result() {
  jq -e --arg session "$SESSION_ID" --arg correlation "$CORRELATION_ID" \
    '.. | objects | select(has("functionResponse") or has("function_response")) | (.functionResponse // .function_response) | select(.name == "persist_session" and .response.session_id == $session and .response.correlation_id == $correlation and .response.stored == true)' \
    "$1" >/dev/null
}

assert_restore_result() {
  jq -e --arg session "$SESSION_ID" --arg marker "$MARKER" --arg correlation "$CORRELATION_ID" \
    '.. | objects | select(has("functionResponse") or has("function_response")) | (.functionResponse // .function_response) | select(.name == "restore_session" and .response.session_id == $session and .response.marker == $marker and .response.correlation_id == $correlation and .response.found == true)' \
    "$1" >/dev/null
}

printf 'trace directory: %s\ncorrelation ID: %s\nsession ID: %s\nmarker: %s\n' \
  "$TRACE_DIR" "$CORRELATION_ID" "$SESSION_ID" "$MARKER"
query "Call persist_session exactly once with session_id=$SESSION_ID, marker=$MARKER, correlation_id=$CORRELATION_ID." \
  | tee "$TRACE_DIR/persist.json"
assert_persist_result "$TRACE_DIR/persist.json" || {
  echo "persist response did not contain the expected successful tool result" >&2
  exit 1
}
query "Call restore_session exactly once with session_id=$SESSION_ID, correlation_id=$CORRELATION_ID." \
  | tee "$TRACE_DIR/restore.json"
assert_restore_result "$TRACE_DIR/restore.json" || {
  echo "restore response did not contain the expected restored marker" >&2
  exit 1
}
printf '\nPASS: persisted and restored the exact session ID, marker, and correlation ID.\nTrace outputs: %s/persist.json and %s/restore.json\n' "$TRACE_DIR" "$TRACE_DIR"
