from types import SimpleNamespace

from app.services.campus_agent.planning_graph import CampusAgentPlanningGraph, StateGraph


class _FakeLLMPlanner:
    def __init__(self):
        self.called = False

    def plan(self, message, *, available_tool_codes=None, memory_context=None):
        self.called = True
        return None


def test_planning_graph_uses_v2_before_llm_for_leave():
    llm = _FakeLLMPlanner()
    graph = CampusAgentPlanningGraph(llm_planner=llm)

    plan = graph.plan("我想请假", available_tool_codes={"create_leave_request"})

    assert plan.tool_code == "create_leave_request"
    assert "v2" in plan.reason
    assert llm.called is False


def test_planning_graph_falls_back_to_rule_planner():
    graph = CampusAgentPlanningGraph(llm_planner=_FakeLLMPlanner())

    plan = graph.plan("查询所有学生", available_tool_codes={"query_student"})

    assert plan.tool_code == "query_student"
    assert "rule" in plan.reason or "graph_trace" in plan.reason


def test_planning_graph_merges_leave_draft_context():
    memory = SimpleNamespace(active_draft={
        "tool_code": "create_leave_request",
        "tool_args": {"reason": "发烧"},
    })
    graph = CampusAgentPlanningGraph(llm_planner=_FakeLLMPlanner())

    plan = graph.plan("明天上午病假", available_tool_codes={"create_leave_request"}, memory_context=memory)

    assert plan.tool_code == "create_leave_request"
    assert plan.args["reason"] == "发烧"
    assert plan.args["leave_type"] == "sick"


def test_langgraph_runtime_is_available_in_current_environment():
    assert StateGraph is not None
