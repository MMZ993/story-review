"""Public API of the review_schemas package.

Deliberate re-exports only: consumers import from `review_schemas`, never from
the internal modules. The surface grows with each Phase 2 increment (errors,
domain models, API/records, MCP) — every shared model named in
docs/design/schemas.md must appear here before Phase 2 closes.
"""
