"""Session-service registration hook for the Agent Engine runtime.

CPython auto-imports sitecustomize from sys.path at interpreter startup;
/app is on PYTHONPATH in the deployed image, so this runs before the
`adk api_server` CLI resolves --session_service_uri, registering the
cloudsql-iam scheme (D24 amendment 1: facilitator sessions in Cloud SQL
PostgreSQL with IAM login).

The services.py mechanism would be the documented hook, but the deployed
runtime loads it only from the agents dir (/app/agents), which adk
staging cannot populate (extra package names may not collide with
"agents").
"""

try:
    from agent_kit.ae_runtime import register_cloudsql_iam_session_service

    register_cloudsql_iam_session_service()
except Exception as exc:  # noqa: BLE001 — fail loud, never half-registered
    import sys

    print(f"sitecustomize: session service registration failed: {exc}", file=sys.stderr)
    raise
