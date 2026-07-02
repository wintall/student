from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.agent import AgentLongTermMemory, AgentPendingAction, AgentTaskDraft
from app.models.base import Base
from app.models.clazz import Clazz
from app.models.conversation import Conversation
from app.models.course import Course
from app.models.department import Department
from app.models.schedule import Classroom, CourseSchedule, Term
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import Menu, Role, RoleMenu, User, UserRole
from app.services.campus_agent.orchestrator import CampusAgentOrchestrator
from app.services.campus_agent.planning_graph import CampusAgentPlanningGraph
from app.services.campus_agent.intent_v2 import plan_v2
from app.services.campus_agent.memory_service import AgentMemoryService
from app.services.campus_agent.tool_handlers import execute_registered_tool


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        Role.__table__,
        Menu.__table__,
        RoleMenu.__table__,
        UserRole.__table__,
        AgentPendingAction.__table__,
        AgentLongTermMemory.__table__,
        Student.__table__,
        Teacher.__table__,
    ])
    session = sessionmaker(bind=engine)()
    user = User(
        id=1,
        username="student01",
        password_hash="x",
        real_name="测试学生",
        email="student01@test.local",
        status=1,
    )
    session.add(user)
    session.commit()
    return session, user


def _add_teacher_profile(db, user):
    teacher = Teacher(
        user_id=user.id,
        employee_no="T2099001",
        name="测试教师",
        gender=1,
        id_card="110101209901010011",
        position="教师",
        status=1,
    )
    db.add(teacher)
    db.commit()
    return teacher


def _academic_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        Role.__table__,
        Menu.__table__,
        RoleMenu.__table__,
        UserRole.__table__,
        Conversation.__table__,
        Department.__table__,
        Teacher.__table__,
        Clazz.__table__,
        Student.__table__,
        Course.__table__,
        Term.__table__,
        Classroom.__table__,
        CourseSchedule.__table__,
        AgentPendingAction.__table__,
        AgentTaskDraft.__table__,
        AgentLongTermMemory.__table__,
    ])
    session = sessionmaker(bind=engine)()
    student_user = User(
        id=10,
        username="student-demo",
        password_hash="x",
        real_name="张芳",
        email="student-demo@test.local",
        status=1,
    )
    admin_user = User(
        id=11,
        username="admin",
        password_hash="x",
        real_name="系统管理员",
        email="admin@test.local",
        status=1,
    )
    counselor_user = User(
        id=12,
        username="teacher-counselor",
        password_hash="x",
        real_name="刘敏",
        email="teacher-counselor@test.local",
        status=1,
    )
    course_teacher_user = User(
        id=13,
        username="teacher-db",
        password_hash="x",
        real_name="李娜",
        email="teacher-db@test.local",
        status=1,
    )
    session.add_all([student_user, admin_user, counselor_user, course_teacher_user])
    session.flush()
    admin_role = Role(id=1, code="admin", name="系统管理员")
    student_role = Role(id=2, code="student", name="学生")
    teacher_role = Role(id=3, code="teacher", name="教师")
    session.add_all([admin_role, student_role, teacher_role])
    session.flush()
    dashboard_menu = Menu(id=1, name="首页", code="dashboard", type=3, status=1)
    my_schedule_menu = Menu(id=2, name="我的课表", code="schedule:my:list", type=3, status=1)
    session.add_all([dashboard_menu, my_schedule_menu])
    session.flush()
    session.add_all([
        RoleMenu(role_id=student_role.id, menu_id=dashboard_menu.id),
        RoleMenu(role_id=student_role.id, menu_id=my_schedule_menu.id),
        RoleMenu(role_id=teacher_role.id, menu_id=dashboard_menu.id),
        RoleMenu(role_id=teacher_role.id, menu_id=my_schedule_menu.id),
    ])
    session.flush()
    session.add_all([
        UserRole(user_id=student_user.id, role_id=student_role.id),
        UserRole(user_id=admin_user.id, role_id=admin_role.id),
        UserRole(user_id=counselor_user.id, role_id=teacher_role.id),
        UserRole(user_id=course_teacher_user.id, role_id=teacher_role.id),
    ])
    session.flush()
    dept = Department(id=1, name="计算机科学与技术学院", code="CS", status=1)
    session.add(dept)
    session.flush()
    counselor = Teacher(
        id=1,
        user_id=counselor_user.id,
        employee_no="T2022004",
        name="刘敏",
        gender=2,
        id_card="110101198001010014",
        position="辅导员",
        title="讲师",
        department_id=dept.id,
        status=1,
    )
    course_teacher = Teacher(
        id=2,
        user_id=course_teacher_user.id,
        employee_no="T2022002",
        name="李娜",
        gender=2,
        id_card="110101198001010015",
        position="院系主任",
        title="副教授",
        department_id=dept.id,
        status=1,
    )
    session.add_all([counselor, course_teacher])
    session.flush()
    clazz = Clazz(
        id=1,
        name="计算机2301班",
        code="CS2301",
        department_id=dept.id,
        grade="2023",
        counselor_id=counselor.id,
        status=1,
    )
    session.add(clazz)
    session.flush()
    student = Student(
        id=1,
        user_id=student_user.id,
        student_no="S20230001",
        name="张芳",
        gender=2,
        id_card="110101200501010011",
        clazz_id=clazz.id,
        status=1,
    )
    no_email_user = User(
        id=14,
        username="student-no-email",
        password_hash="x",
        real_name="吴浩",
        email=None,
        status=1,
    )
    session.add(no_email_user)
    session.flush()
    no_email_student = Student(
        id=2,
        user_id=no_email_user.id,
        student_no="S20230009",
        name="吴浩",
        gender=1,
        id_card="110101200501010019",
        clazz_id=clazz.id,
        status=1,
    )
    course = Course(
        id=1,
        name="数据库原理",
        code="CS302",
        credit=3,
        hours=48,
        course_type=1,
        department_id=dept.id,
        teacher_id=course_teacher.id,
        status=1,
    )
    term = Term(
        id=1,
        name="2025-2026学年第二学期",
        academic_year="2025-2026",
        semester=2,
        start_date=datetime(2026, 2, 23).date(),
        end_date=datetime(2026, 7, 5).date(),
        week_count=18,
        is_current=True,
        status=1,
    )
    classroom = Classroom(id=1, name="A101", building="A楼", room_no="101", campus="主校区", capacity=60, status=1)
    session.add_all([student, no_email_student, course, term, classroom])
    session.flush()
    schedule = CourseSchedule(
        id=1,
        term_id=term.id,
        course_id=course.id,
        clazz_id=clazz.id,
        teacher_id=course_teacher.id,
        classroom_id=classroom.id,
        weekday=1,
        start_section=1,
        end_section=2,
        start_week=1,
        end_week=16,
        week_type="all",
        schedule_type="normal",
        status=1,
    )
    session.add(schedule)
    session.commit()
    return session, student_user, admin_user, course_teacher_user


def _leave_args():
    return {
        "_prepare": True,
        "_session_id": "test-session",
        "leave_type": "sick",
        "start_time": datetime(2099, 1, 1, 8, 0, 0).isoformat(),
        "end_time": datetime(2099, 1, 1, 12, 0, 0).isoformat(),
        "reason": "发烧",
    }


def test_v2_plans_leave_request():
    plan = plan_v2("我想请假")

    assert plan is not None
    assert plan.tool_code == "create_leave_request"


def test_v2_plans_personal_academic_semantics():
    profile = plan_v2("我是谁")
    teachers = plan_v2("我的老师是谁")
    counselor = plan_v2("我的班主任是谁")
    course_teacher = plan_v2("谁教我数据库")
    courses = plan_v2("我有哪些课")

    assert profile.tool_code == "query_my_profile"
    assert teachers.tool_code == "query_my_teachers"
    assert counselor.tool_code == "query_my_teachers"
    assert counselor.args["teacher_scope"] == "counselor"
    assert course_teacher.tool_code == "query_my_teachers"
    assert course_teacher.args["teacher_scope"] == "course"
    assert "数据库" in course_teacher.args["course_keyword"]
    assert courses.tool_code == "query_my_courses"


def test_planning_graph_understands_teacher_update_with_employee_no():
    graph = CampusAgentPlanningGraph()

    plan = graph.plan("吴磊（工号：T2022008）岗位改为辅导员", available_tool_codes={"update_teacher"})

    assert plan.tool_code == "update_teacher"
    assert plan.args["target_keyword"] == "T2022008"
    assert plan.args["changes"]["position"] == "辅导员"


def test_v2_merges_leave_draft_slots():
    memory = SimpleNamespace(active_draft={
        "tool_code": "create_leave_request",
        "tool_args": {"reason": "发烧"},
    })

    plan = plan_v2("明天上午病假", memory_context=memory)

    assert plan.tool_code == "create_leave_request"
    assert plan.args["reason"] == "发烧"
    assert plan.args["leave_type"] == "sick"
    assert plan.args["start_time"].endswith("08:00:00")
    assert plan.args["end_time"].endswith("12:00:00")


def test_create_leave_request_prepare_asks_for_missing_fields():
    db, user = _db()
    _add_teacher_profile(db, user)

    result = execute_registered_tool("create_leave_request", user, {"_prepare": True}, db)

    assert result["status"] == "need_more_info"
    assert "请假类型" in result["data"]["missing_fields"]
    assert "开始时间" in result["data"]["missing_fields"]


def test_create_leave_request_prepare_creates_pending_action():
    db, user = _db()
    _add_teacher_profile(db, user)

    result = execute_registered_tool(
        "create_leave_request",
        user,
        _leave_args(),
        db,
    )

    assert result["status"] == "confirm_required"
    assert result["data"]["pending_action_id"]
    assert "病假" in result["message"]


def test_create_leave_request_prepare_requires_applicant_profile():
    db, user = _db()

    result = execute_registered_tool("create_leave_request", user, _leave_args(), db)

    assert result["status"] == "need_more_info"
    assert "没有关联学生或教职工档案" in result["message"]
    assert "申请人身份" in result["data"]["missing_fields"]


def test_personal_profile_for_admin_without_archive_is_clear():
    db, _student_user, admin_user, _teacher_user = _academic_db()

    result = execute_registered_tool("query_my_profile", admin_user, {}, db)

    assert "系统管理员" in result["message"]
    assert "没有关联学生或教职工档案" in result["message"]
    assert result["data"]["student"] is None
    assert result["data"]["teacher"] is None


def test_student_can_query_my_teachers_and_course_teacher():
    db, student_user, _admin_user, _teacher_user = _academic_db()

    all_teachers = execute_registered_tool("query_my_teachers", student_user, {}, db)
    db_teacher = execute_registered_tool(
        "query_my_teachers",
        student_user,
        {"teacher_scope": "course", "course_keyword": "数据库"},
        db,
    )

    assert "班主任/辅导员" in all_teachers["message"]
    assert "刘敏" in all_teachers["message"]
    assert "数据库原理" in all_teachers["message"]
    assert "李娜" in db_teacher["message"]


def test_student_can_query_my_courses():
    db, student_user, _admin_user, _teacher_user = _academic_db()

    result = execute_registered_tool("query_my_courses", student_user, {}, db)

    assert "数据库原理" in result["message"]
    assert result["data"]["total"] == 1


def test_teacher_can_query_own_profile_and_courses():
    db, _student_user, _admin_user, teacher_user = _academic_db()

    profile = execute_registered_tool("query_my_profile", teacher_user, {}, db)
    courses = execute_registered_tool("query_my_courses", teacher_user, {}, db)

    assert "教职工档案" in profile["message"]
    assert "李娜" in profile["message"]
    assert "数据库原理" in courses["message"]


def test_manual_academic_mode_keeps_who_am_i_in_profile_tool():
    db, _student_user, _admin_user, teacher_user = _academic_db()
    conversation = Conversation(user_id=teacher_user.id, session_id="manual-academic-profile", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()

    response = CampusAgentOrchestrator(db).chat(
        user=teacher_user,
        conversation=conversation,
        session_id="manual-academic-profile",
        message="我是谁",
        mode="academic_ops",
    )

    assert response.mode == "academic_ops"
    assert response.intent == "query_my_profile"
    assert "教职工档案" in response.reply
    assert "心理支持" not in response.reply


def test_manual_rag_mode_ignores_active_academic_draft(monkeypatch):
    db, _student_user, admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=admin_user.id, session_id="rag-ignore-draft", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()
    agent = CampusAgentOrchestrator(db)
    monkeypatch.setattr(
        "app.services.campus_agent.orchestrator.rag_knowledge_service.answer",
        lambda **kwargs: {
            "answer": "十常侍是东汉末年宦官集团。",
            "sources": [{"chunk_id": 1, "title": "三国演义", "chunk_no": 13, "score": 1}],
        },
    )

    first = agent.chat(
        user=admin_user,
        conversation=conversation,
        session_id="rag-ignore-draft",
        message="我想增加一个学生",
        mode="academic_ops",
    )
    second = agent.chat(
        user=admin_user,
        conversation=conversation,
        session_id="rag-ignore-draft",
        message="十常侍是谁啊",
        mode="rag",
    )

    assert first.intent == "create_student"
    assert "新增学生还缺少" in first.reply
    assert second.mode == "rag"
    assert second.intent == "rag_knowledge_ask"
    assert "新增学生还缺少" not in second.reply


def test_master_agent_dispatches_personal_relation_query():
    db, student_user, _admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=student_user.id, session_id="master-agent-test", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()

    response = CampusAgentOrchestrator(db).chat(
        user=student_user,
        conversation=conversation,
        session_id="master-agent-test",
        message="我的老师是谁",
        mode="auto",
    )

    assert response.intent == "query_my_teachers"
    assert "刘敏" in response.reply
    assert "李娜" in response.reply


def test_student_followup_asks_what_recent_teachers_teach():
    db, student_user, _admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=student_user.id, session_id="teacher-course-followup", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()
    agent = CampusAgentOrchestrator(db)

    first = agent.chat(
        user=student_user,
        conversation=conversation,
        session_id="teacher-course-followup",
        message="我的老师是谁",
        mode="auto",
    )
    second = agent.chat(
        user=student_user,
        conversation=conversation,
        session_id="teacher-course-followup",
        message="他们教什么",
        mode="auto",
    )

    assert first.intent == "query_my_teachers"
    assert second.intent == "query_my_teacher_courses_followup"
    assert "数据库原理" in second.reply
    assert "李娜" in second.reply


def test_student_followup_email_to_recent_teacher_requires_selection_when_multiple():
    db, student_user, _admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=student_user.id, session_id="teacher-email-followup", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()
    agent = CampusAgentOrchestrator(db)

    agent.chat(
        user=student_user,
        conversation=conversation,
        session_id="teacher-email-followup",
        message="我的老师是谁",
        mode="auto",
    )
    response = agent.chat(
        user=student_user,
        conversation=conversation,
        session_id="teacher-email-followup",
        message="给老师发邮件",
        mode="auto",
    )

    assert response.intent == "context_reference_clarify"
    assert "多位老师" in response.reply
    assert "刘敏" in response.reply
    assert "李娜" in response.reply


def test_admin_email_to_student_without_email_guides_contact_update():
    db, _student_user, admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=admin_user.id, session_id="missing-email-test", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()

    response = CampusAgentOrchestrator(db).chat(
        user=admin_user,
        conversation=conversation,
        session_id="missing-email-test",
        message="给吴浩同学发个邮件",
        mode="auto",
    )

    assert response.intent == "send_email"
    assert "吴浩" in response.reply
    assert "还没有邮箱" in response.reply
    assert "把吴浩邮箱改为" in response.reply


def test_master_agent_handles_teacher_age_with_privacy_boundary():
    db, student_user, _admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=student_user.id, session_id="teacher-age-test", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()

    response = CampusAgentOrchestrator(db).chat(
        user=student_user,
        conversation=conversation,
        session_id="teacher-age-test",
        message="我的老师的年龄",
        mode="auto",
    )

    assert response.intent in {"academic_relation_need_clarification", "academic_relation_privacy_limited"}
    assert "老师" in response.reply


def test_master_agent_routes_study_module_without_academic_leak():
    db, student_user, _admin_user, _teacher_user = _academic_db()
    conversation = Conversation(user_id=student_user.id, session_id="study-route-test", messages=[], book_codes=[])
    db.add(conversation)
    db.commit()

    response = CampusAgentOrchestrator(db).chat(
        user=student_user,
        conversation=conversation,
        session_id="study-route-test",
        message="讲解一下牛顿第二定律",
        mode="auto",
    )

    assert response.mode == "study"
    assert response.intent.startswith("learning_")


def test_long_term_memory_write_and_recall():
    db, user = _db()
    service = AgentMemoryService(db)

    service.remember_event(
        user=user,
        module_code="campus_agent",
        event_type="preference",
        content="用户偏好：请用简洁中文回答学习问题",
        payload={"importance": 3},
    )
    memories = service.recall_long_term(
        user=user,
        module_code="campus_agent",
        query="学习问题",
    )

    assert memories
    assert memories[0]["memory_type"] == "preference"
