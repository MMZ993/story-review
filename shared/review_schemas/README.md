# review_schemas

Shared Pydantic v2 contract models for the story-review capstone: HTTP API
payloads, agent/MCP tool inputs and outputs, and durable persistence records.

The authoritative field-level specification is `docs/design/schemas.md` in the
repository root. This package implements that specification exactly; changing a
model is a contract change and requires a semantic-version bump.

Public API: import from `review_schemas` (the package `__init__` re-exports the
stable consumer surface). Modules are implementation details.

Version: 0.1.0 (Phase 2). Local-only; no runtime services.
