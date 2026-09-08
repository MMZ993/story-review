"""Public API of the ado_wire package.

Pure Azure DevOps wire models (verbatim work-item and comment payload
shapes) shared by the dataset loader and the story-MCP preparation step.
Deliberate re-exports only: consumers import from ``ado_wire``.
"""

from ado_wire.wire import WorkItem, WorkItemComment

__all__ = ["WorkItem", "WorkItemComment"]
