from types import SimpleNamespace

from app.services.campus_agent.planner import CampusAgentPlanner
from app.services.campus_agent.orchestrator import _has_active_task_draft, _should_resume_academic_draft
from app.services.campus_agent.resolver import CampusAgentResolver
from app.services.campus_agent.intent_router import route_intent
from app.services.campus_agent.intent_v2 import plan_v2
from app.services.campus_agent.tool_handlers import normalize_args


def _teacher_memory():
    return SimpleNamespace(
        active_draft=None,
        recent_query_tool={
            "tool_code": "query_teacher",
            "tool_args": {"keyword": "T2022008"},
            "tool_status": "success",
            "tool_data": {
                "total": 1,
                "items": [{"id": 8, "name": "吴磊", "employee_no": "T2022008", "position": "教师"}],
            },
        },
        last_tool={
            "tool_code": "update_teacher",
            "tool_args": {"target_keyword": "T2022008"},
            "tool_status": "success",
            "tool_data": {"id": 8, "name": "吴磊", "employee_no": "T2022008", "position": "教师"},
        },
        messages=[],
    )


def _student_memory():
    return SimpleNamespace(
        active_draft=None,
        recent_query_tool={
            "tool_code": "query_student",
            "tool_args": {"keyword": "S20230001"},
            "tool_status": "success",
            "tool_data": {
                "total": 1,
                "items": [{"id": 1, "name": "张芳", "student_no": "S20230001", "gender": 2}],
            },
        },
        last_tool={
            "tool_code": "update_student",
            "tool_args": {"target_keyword": "S20230001"},
            "tool_status": "success",
            "tool_data": {"id": 1, "name": "张芳", "student_no": "S20230001", "gender": 1},
        },
        messages=[],
    )


def _email_draft_memory():
    return SimpleNamespace(
        active_draft={
            "tool_code": "send_email",
            "tool_args": {
                "recipient_keyword": "张芳",
                "recipient_email": "s20230001@student.local",
            },
            "tool_status": "need_more_info",
            "tool_data": {"missing_fields": ["主题", "正文"]},
        },
        recent_query_tool=None,
        last_tool={
            "tool_code": "send_email",
            "tool_args": {
                "recipient_keyword": "张芳",
                "recipient_email": "s20230001@student.local",
            },
            "tool_status": "need_more_info",
            "tool_data": {"missing_fields": ["主题", "正文"]},
        },
        messages=[],
    )


def _plan(message, memory=None):
    planner = CampusAgentPlanner(llm_planner=None)
    resolver = CampusAgentResolver()
    available = {
        "query_student",
        "update_student",
        "query_teacher",
        "update_teacher",
        "query_course",
        "update_course",
        "send_email",
        "send_bulk_email",
        "query_weather",
    }
    plan = planner.plan(message, mode="auto", available_tool_codes=available, memory_context=memory)
    return resolver.resolve(plan, message, memory)


def _normalized(message, memory=None):
    plan = _plan(message, memory)
    args = normalize_args(plan.tool_code, message, plan.args) if plan.tool_code else {}
    return plan.tool_code, args


def test_teacher_update_with_employee_no_is_update_not_query():
    tool, args = _normalized("吴磊（工号：T2022008）岗位改为辅导员")

    assert tool == "update_teacher"
    assert args["target_keyword"] == "T2022008"
    assert args["changes"] == {"position": "辅导员"}


def test_teacher_query_with_employee_no_is_query():
    tool, args = _normalized("查询吴磊（T2022008）")

    assert tool == "query_teacher"
    assert args["keyword"] == "T2022008"


def test_teacher_followup_uses_recent_teacher_context():
    tool, args = _normalized("这个人岗位是什么", _teacher_memory())

    assert tool == "query_teacher"
    assert args["keyword"] == "T2022008"
    assert args["requested_field"] == "position"


def test_student_update_with_student_no_is_update_not_query():
    tool, args = _normalized("张芳（学号：S20230001）性别改为男")

    assert tool == "update_student"
    assert args["target_keyword"] == "S20230001"
    assert args["changes"] == {"gender": 1}


def test_student_query_with_student_no_is_query():
    tool, args = _normalized("查询张芳（S20230001）")

    assert tool == "query_student"
    assert args["keyword"] == "S20230001"


def test_student_followup_uses_recent_student_context():
    tool, args = _normalized("这个人性别是什么", _student_memory())

    assert tool == "query_student"
    assert args["keyword"] == "S20230001"
    assert args["requested_field"] == "gender"


def test_course_update_not_swallowed_by_query():
    tool, args = _normalized("把高等数学学分改成4")

    assert tool == "update_course"
    assert args["target_keyword"] == "高等数学"
    assert args["changes"] == {"credit": "4"}


def test_email_intent_keeps_recipient_and_missing_content():
    tool, args = _normalized("给学生吴浩发邮件")

    assert tool == "send_email"
    assert args["recipient_keyword"] == "吴浩"


def test_email_recipient_suffix_title_is_cleaned():
    tool, args = _normalized("给吴浩同学发个邮件")

    assert tool == "send_email"
    assert args["recipient_keyword"] == "吴浩"


def test_email_recipient_with_angle_email_is_cleaned():
    tool, args = _normalized("给张芳 <s20230001@student.local>发送邮件")

    assert tool == "send_email"
    assert args["recipient_keyword"] == "张芳"
    assert args["recipient_email"] == "s20230001@student.local"


def test_email_draft_followup_keeps_recipient_and_adds_subject_body():
    tool, args = _normalized("主题安慰信 正文 不要难受", _email_draft_memory())

    assert tool == "send_email"
    assert args["recipient_keyword"] == "张芳"
    assert args["recipient_email"] == "s20230001@student.local"
    assert args["subject"] == "安慰信"
    assert args["body"] == "不要难受"


def test_student_email_update_intent_with_missing_email_value():
    tool, args = _normalized("能补充吴浩的邮箱吗")

    assert tool == "update_student"
    assert args["target_keyword"] == "吴浩"
    assert not args.get("changes")


def test_student_email_update_intent_with_email_value():
    tool, args = _normalized("给吴浩补充邮箱 s20230009@student.local")

    assert tool == "update_student"
    assert args["target_keyword"] == "吴浩"
    assert args["changes"] == {"email": "s20230009@student.local"}


def test_active_email_draft_has_task_priority():
    assert _has_active_task_draft(_email_draft_memory()) is True


def test_academic_draft_only_resumes_in_auto_or_academic_modes():
    memory = _email_draft_memory()

    assert _should_resume_academic_draft(memory, "auto", "主题是测试 内容是hello")
    assert _should_resume_academic_draft(memory, "academic_ops", "主题是测试 内容是hello")
    assert not _should_resume_academic_draft(memory, "rag", "十常侍是谁")
    assert not _should_resume_academic_draft(memory, "document", "总结这个文件")


def test_weather_query():
    tool, args = _normalized("查询深圳天气")

    assert tool == "query_weather"


def test_router_routes_learning_poetry():
    route = route_intent("赏析一下将进酒吧", allow_llm=False)

    assert route.mode == "study"


def test_router_routes_learning_concept():
    route = route_intent("讲解一下牛顿第二定律", allow_llm=False)

    assert route.mode == "study"


def test_router_routes_github_issue_creation():
    route = route_intent("创建一个 issue，标题是优化助手，内容是补充 GitHub 模块测试", allow_llm=False)

    assert route.mode == "github"


def test_router_routes_multi_stop_map():
    route = route_intent("从石芽岭地铁站到深圳大学再到深圳人才公园规划一下路线", allow_llm=False)

    assert route.mode == "map"


def test_router_routes_public_search():
    route = route_intent("世界杯射手王", allow_llm=False)

    assert route.mode == "worldcup"


def test_router_routes_data_analysis():
    route = route_intent("分析一下学生成绩趋势和挂科情况", allow_llm=False)

    assert route.mode == "data_analysis"


def test_router_routes_ai_knowledge():
    route = route_intent("LangGraph 和 LangChain 有什么区别", allow_llm=False)

    assert route.mode == "ai_knowledge"


def test_router_keeps_teacher_query_in_academic_ops():
    route = route_intent("吴磊（工号：T2022008）岗位是什么", allow_llm=False)

    assert route.mode == "academic_ops"


def test_router_treats_who_am_i_as_academic_profile():
    route = route_intent("我是谁", allow_llm=True)

    assert route.mode == "academic_ops"
    assert route.source == "deterministic"


def test_continue_all_keeps_previous_query_context():
    tool, args = _normalized("能显示全部吗", SimpleNamespace(
        active_draft=None,
        recent_query_tool={
            "tool_code": "query_course",
            "tool_args": {"page": 1, "limit": 8},
            "tool_status": "success",
            "tool_data": {"total": 12, "items": [{"id": 1}, {"id": 2}]},
        },
        last_tool=None,
        messages=[],
    ))

    assert tool == "query_course"
    assert args["page"] == 1
    assert args["limit"] == 12


def test_show_all_students_does_not_reuse_first_student_as_keyword():
    tool, args = _normalized("显示所有", SimpleNamespace(
        active_draft=None,
        recent_query_tool={
            "tool_code": "query_student",
            "tool_args": {"page": 1, "limit": 8},
            "tool_status": "success",
            "tool_data": {
                "total": 56,
                "items": [{"id": 1, "name": "张芳", "student_no": "S20230001"}],
            },
        },
        last_tool={
            "tool_code": "query_student",
            "tool_args": {"page": 1, "limit": 8},
            "tool_status": "success",
            "tool_data": {
                "total": 56,
                "items": [{"id": 1, "name": "张芳", "student_no": "S20230001"}],
            },
        },
        messages=[],
    ))

    assert tool == "query_student"
    assert args["page"] == 1
    assert args["limit"] == 56
    assert "keyword" not in args


def test_leave_request_to_teacher_is_create_leave_intent():
    plan = plan_v2("我要向老师请假")

    assert plan.tool_code == "create_leave_request"


def test_teacher_course_followup_uses_my_teachers_context():
    memory = SimpleNamespace(
        active_draft=None,
        recent_query_tool=None,
        last_tool={
            "tool_code": "query_my_teachers",
            "tool_args": {},
            "tool_status": "success",
            "tool_data": {
                "course_teachers": [
                    {"course_id": 1, "course_name": "数据库原理", "teacher": {"id": 2, "name": "李娜"}}
                ]
            },
        },
        messages=[
            {
                "role": "assistant",
                "tool_code": "query_my_teachers",
                "tool_data": {
                    "course_teachers": [
                        {"course_id": 1, "course_name": "数据库原理", "teacher": {"id": 2, "name": "李娜"}}
                    ]
                },
            }
        ],
    )
    plan = plan_v2("他们教什么", memory_context=memory)

    assert plan.tool_code == "query_my_teachers"
    assert plan.args["_relation_followup"] == "teacher_courses"


def test_emotion_words_win_over_teacher_academic_signal():
    from app.services.campus_agent.intent_router import route_intent, should_override_current_mode

    samples = [
        "两个项目老师老师push我，我很难受",
        "老师一直催我我很焦虑",
        "我最近被老师催得压力很大",
    ]
    for text in samples:
        route = route_intent(text, allow_llm=False)
        assert route.mode == "emotion"
        assert not should_override_current_mode("emotion", route)


def test_my_teacher_question_still_goes_academic():
    from app.services.campus_agent.intent_router import route_intent

    route = route_intent("我的老师是谁", allow_llm=False)

    assert route.mode == "academic_ops"


def test_manual_mode_should_be_sticky_in_chat_entry():
    from app.services.campus_agent.orchestrator import should_override_current_mode, route_intent

    route = route_intent("我的老师是谁", allow_llm=False)

    assert route.mode == "academic_ops"
    # The helper may still describe a possible override for legacy callers, but
    # the real chat entry no longer uses it for manually selected modules.
    assert should_override_current_mode("emotion", route) is False


if __name__ == "__main__":
    import traceback

    failed = 0
    current = globals()
    for name in sorted(key for key in current if key.startswith("test_")):
        try:
            current[name]()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
