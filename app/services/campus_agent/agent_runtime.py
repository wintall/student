"""Extensible runtime facade for the football assistant.

The project can run without LangGraph/deepagents/MCP installed, but this facade
keeps our module handlers shaped like graph nodes and MCP-style tools.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

try:  # Optional: real LangGraph runtime when installed.
    from langgraph.graph import END, StateGraph  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    END = "__end__"
    StateGraph = None


AgentNode = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class RuntimeTool:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    module: str = "general"

    def invoke(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.handler(args or {})


@dataclass
class RuntimeResult:
    reply: str
    intent: str
    data: dict[str, Any] = field(default_factory=dict)
    references: list[dict] = field(default_factory=list)


class MCPToolAdapter:
    """Local MCP-style tool registry.

    This is deliberately simple: modules call named tools through a stable
    adapter today; later the handlers can be exposed through an actual MCP
    server without changing module code.
    """

    def __init__(self):
        self._tools: dict[str, RuntimeTool] = {}

    def register(self, tool: RuntimeTool) -> None:
        self._tools[tool.name] = tool

    def invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"ok": False, "error": f"工具 {name} 未注册"}
        return tool.invoke(args)

    def list_tools(self) -> list[dict]:
        return [
            {"name": item.name, "description": item.description, "module": item.module}
            for item in self._tools.values()
        ]


class AssistantGraphRuntime:
    """Tiny graph runner with optional LangGraph compatibility."""

    def __init__(self):
        self.mcp = MCPToolAdapter()

    def run_linear(self, state: dict[str, Any], nodes: list[AgentNode]) -> dict[str, Any]:
        current = dict(state)
        for node in nodes:
            current = node(current)
        return current

    def build_langgraph(self, nodes: dict[str, AgentNode], entry: str):
        if StateGraph is None:
            return None
        graph = StateGraph(dict)
        for name, node in nodes.items():
            graph.add_node(name, node)
        ordered = list(nodes)
        for idx, name in enumerate(ordered):
            graph.add_edge(name, ordered[idx + 1] if idx + 1 < len(ordered) else END)
        graph.set_entry_point(entry)
        return graph.compile()


try:  # Optional future hook.
    import deepagents as deepagents_package  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    deepagents_package = None


def deepagents_available() -> bool:
    return deepagents_package is not None


def build_default_runtime() -> AssistantGraphRuntime:
    """Build the local MCP-style runtime used by assistant capability modules."""
    runtime = AssistantGraphRuntime()
    try:
        from app.services.campus_agent.web_search_tools import search_web

        runtime.mcp.register(RuntimeTool(
            name="web_search",
            description="Search the web and return structured results with source links.",
            handler=lambda args: search_web(
                str(args.get("query") or ""),
                limit=int(args.get("limit") or 6),
                fresh=bool(args.get("fresh")),
            ),
            module="search",
        ))
    except Exception:
        pass
    return runtime
