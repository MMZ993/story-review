# ado_wire

Shared Pydantic v2 wire models for verbatim Azure DevOps payloads:
``WorkItem`` (REST / `az boards work-item show --expand all` shape) and
``WorkItemComment`` (comments-API shape).

These are pure wire models — extra fields are kept verbatim, validation is
deliberately minimal (the fields the review pipeline consumes must exist).
Consumers: the dataset-loader ``StoryEnvelope`` export wrapper and the
story-MCP preparation step (which also serves live ADO responses).

Public API: import from ``ado_wire`` (the package ``__init__`` re-exports
the stable surface). The internal module name is an implementation detail.

Version: 0.1.0. Local-only; no runtime services.
