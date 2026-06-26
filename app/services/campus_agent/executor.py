"""Safe execution gateway for campus assistant tools."""
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.permissions import has_permission
from app.models.user import User
from app.services.campus_agent.registry import AgentTool, get_tool
from app.services.campus_agent.tool_handlers import execute_registered_tool


@dataclass
class ToolExecutionResult:
    success: bool
    message: str
    tool: str | None = None
    status: str = "skipped"
    data: Any = None
    confirm_required: bool = False
    risk: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "status": self.status,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "confirm_required": self.confirm_required,
            "risk": self.risk,
        }


class CampusAgentExecutor:
    """Central guardrail for all assistant-triggered system operations."""

    def __init__(self, db: Session):
        self.db = db

    def validate_tool_access(self, user: User, tool_code: str) -> tuple[AgentTool | None, ToolExecutionResult | None]:
        tool = get_tool(tool_code)
        if not tool:
            return None, ToolExecutionResult(
                success=False,
                tool=tool_code,
                status="not_found",
                message="该工具暂未开放，足球助手不能执行未登记的系统操作。",
            )

        if not has_permission(user, self.db, tool.permission):
            return tool, ToolExecutionResult(
                success=False,
                tool=tool.code,
                status="permission_denied",
                message=f"你当前没有“{tool.name}”权限，所需权限码：{tool.permission}。",
                risk=tool.risk,
            )

        return tool, None

    def execute(self, user: User, tool_code: str, args: dict | None = None, confirmed: bool = False) -> ToolExecutionResult:
        tool, error = self.validate_tool_access(user, tool_code)
        if error:
            return error
        assert tool is not None

        if tool.confirm_required and not confirmed:
            return ToolExecutionResult(
                success=False,
                tool=tool.code,
                status="confirm_required",
                message=f"我识别到你要执行“{tool.name}”。该操作风险等级为 {tool.risk}，需要确认后才能继续。",
                confirm_required=True,
                risk=tool.risk,
                data={"tool": tool.code, "args": args or {}},
            )

        tool_payload = execute_registered_tool(tool.code, user, args or {}, self.db)
        if tool_payload is not None:
            return ToolExecutionResult(
                success=True,
                tool=tool.code,
                status="success",
                message=tool_payload.get("message") or f"“{tool.name}”执行成功。",
                risk=tool.risk,
                data=tool_payload.get("data"),
            )

        return ToolExecutionResult(
            success=False,
            tool=tool.code,
            status="handler_missing",
            message=f"“{tool.name}”已经通过权限校验，但第一步只完成工具白名单和权限映射，具体执行器会在下一步接入。",
            risk=tool.risk,
            data={"tool": tool.to_dict(), "args": args or {}},
        )
