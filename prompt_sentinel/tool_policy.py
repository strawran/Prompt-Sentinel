"""Allowlisted tool execution for Agent integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .audit import AuditStore


class ToolRejected(RuntimeError):
    """A model-requested tool call was rejected before execution."""


@dataclass(frozen=True)
class ToolSpec:
    validate: Callable[[dict], bool]
    execute: Callable[[dict], str]


class ToolPolicy:
    def __init__(
        self,
        allowed_tools: frozenset[str],
        registry: Mapping[str, ToolSpec],
        audit: AuditStore,
    ) -> None:
        self.allowed_tools = allowed_tools
        self.registry = registry
        self.audit = audit

    def run(self, name: str, arguments: object, request_id: str) -> str:
        if name not in self.allowed_tools:
            reason = "tool_not_allowed"
        elif name not in self.registry:
            reason = "tool_not_registered"
        elif not isinstance(arguments, dict) or not self.registry[name].validate(arguments):
            reason = "invalid_arguments"
        else:
            reason = ""
        if reason:
            self.audit.add_tool(request_id, name, "deny", reason)
            raise ToolRejected(f"Tool call denied: {reason}")

        self.audit.add_tool(request_id, name, "allow", "allowlisted_and_validated")
        try:
            return self.registry[name].execute(arguments)
        except Exception as exc:
            self.audit.add_tool(request_id, name, "error", "handler_failed")
            raise ToolRejected("Tool handler failed") from exc
