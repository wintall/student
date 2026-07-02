"""Shared schemas for the campus agent orchestration pipeline."""
from dataclasses import dataclass, field
from typing import Any, Literal


PlanStatus = Literal["planned", "clarify", "unmatched"]


@dataclass
class AgentPlan:
    tool_code: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    status: PlanStatus = "unmatched"
    intent: str = "unmatched"
    confidence: float = 0.0
    response_mode: str = "academic_ops"
    needs_confirmation: bool = False
    reason: str = ""

    @property
    def has_tool(self) -> bool:
        return bool(self.tool_code)


@dataclass
class AgentResponse:
    reply: str
    mode: str
    intent: str
    tool_calls: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    suggested_mode: str | None = None

