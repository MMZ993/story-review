#!/usr/bin/env bash
# Shared staging helpers for deploy/agents/*/deploy.sh (Phase 8 increment 3).
#
# `adk deploy agent_engine` stages one agent directory (its __init__.py
# exposing root_agent, a requirements.txt installed into the built image,
# optional .env runtime vars and .agent_engine_config.json) plus
# --extra_packages entries placed at /app/<name> (PYTHONPATH=/app). The
# helper below stages the shared runtime from the repository root per
# docs/operations/deployment.md: agent package + config.yaml, agent_kit,
# review_schemas, and prompts (PROMPTS_DIR=/app/prompts).
#
# Versioning: every deploy creates a NEW versioned Agent Engine resource
# labeled <slug>-<short-sha> (deployment.md "Versioning and rollback");
# no in-place mutation of running resources.

# agents_stage <slug> <pkg> <stage_dir> — build the staged agent dir and
# extra-packages list; prints "stage_dir agent_dir extra1 extra2 ...".
# The staged dir name must be a valid Python module (underscores); the
# versioned display name keeps the repository slug's hyphens.
agents_stage() {
    local slug="$1" pkg="$2" stage="$3"
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"

    local agent_dir="$stage/${pkg}_ae"
    mkdir -p "$agent_dir" "$stage/extra"

    cp "$script_dir/agent_src/__init__.py" "$agent_dir/"
    cp "$script_dir/agent_src/requirements.txt" "$agent_dir/"
    if [ -f "$script_dir/agent_src/services.py" ]; then
        cp "$script_dir/agent_src/services.py" "$agent_dir/"
    fi

    # Agent package + immutable config staged as one extra package so
    # load_config() finds config.yaml inside the package dir.
    cp -r "agents/$slug/$pkg" "$stage/extra/$pkg"
    cp "agents/$slug/config.yaml" "$stage/extra/$pkg/config.yaml"
    local extras="$stage/extra/$pkg"

    # Custom session services register via sitecustomize.py (see
    # agent_src/sitecustomize.py): the deployed `adk api_server` loads
    # services.py only from the agents dir (/app/agents), which an extra
    # package cannot populate (name conflict with adk's own staging) —
    # but /app IS on PYTHONPATH, and CPython auto-imports sitecustomize
    # from sys.path at interpreter startup, before the CLI resolves the
    # session service.
    if [ -f "$script_dir/agent_src/sitecustomize.py" ]; then
        cp "$script_dir/agent_src/sitecustomize.py" "$stage/extra/sitecustomize.py"
        extras="$extras $stage/extra/sitecustomize.py"
    fi

    echo "$stage $agent_dir $extras prompts shared/agent_kit/agent_kit shared/review_schemas/review_schemas"
}

# agents_env <slug> — runtime .env lines common to every agent.
agents_env() {
    printf 'PROMPTS_DIR=/app/prompts\n'
}

# agents_config <slug> <service_account> — .agent_engine_config.json body.
agents_config() {
    printf '{"service_account": "%s"}\n' "$2"
}

# agents_deploy <slug> <stage> <agent_dir> <extras...> — run the ADK
# Agent Engine deployment as a new versioned resource; prints the created
# resource name for the runbook / env pointer.
agents_deploy() {
    local slug="$1" stage="$2" agent_dir="$3"; shift 3
    local sha="$(git rev-parse --short HEAD)"
    local version="$slug-$sha"
    if ! git diff --quiet || ! git diff --cached --quiet; then
        # The version label maps resources to commits (deployment.md
        # tag↔resource map). Deploying uncommitted code breaks that map —
        # require an explicit opt-in and mark the label.
        if [ "${ALLOW_DIRTY_DEPLOY:-}" = "1" ]; then
            version="$version-dirty"
            echo "WARNING: dirty tree deploy (ALLOW_DIRTY_DEPLOY=1): label $version" >&2
        else
            echo "refusing to deploy: working tree has uncommitted changes" >&2
            echo "commit first, or set ALLOW_DIRTY_DEPLOY=1 to label -dirty" >&2
            return 2
        fi
    fi
    local extra_args=()
    local p
    for p in "$@"; do extra_args+=(--extra_packages "$p"); done

    local session_arg=()
    if [ -n "${AE_SESSION_SERVICE_URI:-}" ]; then
        session_arg=(--session_service_uri "$AE_SESSION_SERVICE_URI")
    fi
    # temp_folder inside our staging dir so the generated build context
    # survives for inspection when a deployment fails to start.
    local temp_arg=(--temp_folder "$stage/aetmp")

    echo "deploying $version (staging under $stage)"
    uv run --no-project --quiet --with "google-adk[mcp,db]==2.8.0" --with google-cloud-aiplatform \
        adk deploy agent_engine \
        --project "$PROJECT_ID" --region "$REGION" \
        --display_name "$version" --description "$slug $sha" \
        "${session_arg[@]}" "${temp_arg[@]}" "${extra_args[@]}" \
        "$agent_dir" >"$stage/deploy.log" 2>&1
    local rc=$?
    grep -E "Created a new instance|Deployed to Agent Platform|Error|error" "$stage/deploy.log" || true
    return $rc
}
