"""LangGraph-compatible planning graph for academic tool operations."""
from __future__ import annotations

from typing import Any

from app.services.campus_agent.intent_v2 import plan_v2
from app.services.campus_agent.llm_planner import CampusAgentLLMPlanner
from app.services.campus_agent.planner import CampusAgentPlanner
from app.services.campus_agent.schemas import AgentPlan

try:
    from langgraph.graph import END, StateGraph  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    END = "__end__"
    StateGraph = None


class CampusAgentPlanningGraph:
    """Plan a tool call with V2 rules, structured LLM, then rule fallback.

    The graph only decides intent and slots. Permission checks, confirmations,
    and real business execution stay in CampusAgentExecutor and tool handlers.
    """

    def __init__(self, *, llm_planner: CampusAgentLLMPlanner | None = None):
        self.llm_planner = llm_planner or CampusAgentLLMPlanner()
        self.rule_planner = CampusAgentPlanner(llm_planner=None)
        self._compiled = self._build_graph()

    def plan(
        self,
        message: str,
        *,
        mode: str = "auto",
        available_tool_codes: set[str] | None = None,
        memory_context: Any | None = None,
    ) -> AgentPlan:
        state = {
            "message": message,
            "mode": mode,
            "available_tool_codes": set(available_tool_codes or set()),
            "memory_context": memory_context,
            "plan": None,
            "trace": [],
        }
        if self._compiled is not None:
            result = self._compiled.invoke(state)
        else:
            result = self._run_linear(state)
        plan = result.get("plan")
        if isinstance(plan, AgentPlan):
            if result.get("trace"):
                plan.reason = f"{plan.reason}|graph_trace:{'->'.join(result['trace'])}"
            return plan
        return AgentPlan(status="unmatched", intent="unmatched", confidence=0.0, reason="planning_graph_unmatched")

    def _run_linear(self, state: dict) -> dict:
        current = self._v2_node(state)
        current = self._llm_node(current)
        current = self._rule_node(current)
        return current

    def _build_graph(self):
        if StateGraph is None:
            return None
        graph = StateGraph(dict)
        graph.add_node("v2_intent", self._v2_node)
        graph.add_node("structured_llm", self._llm_node)
        graph.add_node("rule_fallback", self._rule_node)
        graph.add_edge("v2_intent", "structured_llm")
        graph.add_edge("structured_llm", "rule_fallback")
        graph.add_edge("rule_fallback", END)
        graph.set_entry_point("v2_intent")
        try:
            return graph.compile()
        except Exception:
            return None

    def _has_plan(self, state: dict) -> bool:
        plan = state.get("plan")
        return isinstance(plan, AgentPlan) and bool(plan.tool_code)

    def _v2_node(self, state: dict) -> dict:
        if self._has_plan(state):
            return state
        plan = plan_v2(state.get("message") or "", memory_context=state.get("memory_context"))
        trace = list(state.get("trace") or [])
        if plan and plan.tool_code:
            state["plan"] = plan
            trace.append("v2")
        else:
            trace.append("v2_none")
        state["trace"] = trace
        return state

    def _llm_node(self, state: dict) -> dict:
        if self._has_plan(state):
            return state
        plan = self.llm_planner.plan(
            state.get("message") or "",
            available_tool_codes=state.get("available_tool_codes") or set(),
            memory_context=state.get("memory_context"),
        )
        trace = list(state.get("trace") or [])
        if plan and plan.tool_code:
            state["plan"] = plan
            trace.append("llm")
        else:
            trace.append("llm_none")
        state["trace"] = trace
        return state

    def _rule_node(self, state: dict) -> dict:
        if self._has_plan(state):
            return state
        plan = self.rule_planner.plan(
            state.get("message") or "",
            mode=state.get("mode") or "auto",
            available_tool_codes=state.get("available_tool_codes") or set(),
            memory_context=state.get("memory_context"),
        )
        trace = list(state.get("trace") or [])
        if plan and plan.tool_code:
            trace.append("rule")
        else:
            trace.append("rule_none")
        state["trace"] = trace
        state["plan"] = plan
        return state
