"""Campus assistant orchestration pipeline."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.user import User
from app.services import email_service, rag_knowledge_service
from app.services.campus_agent.agent_runtime import build_default_runtime
from app.services.campus_agent.code_analysis_tools import (
    analyze_code_message,
    handle_coding_assistant_message,
    _looks_like_project_analysis,
)
from app.services.campus_agent.data_analysis_tools import handle_data_analysis_message
from app.services.campus_agent.document_tools import handle_document_message, resolve_agent_file
from app.services.campus_agent.emotion_tools import handle_emotion_message
from app.services.campus_agent.executor import CampusAgentExecutor
from app.services.campus_agent.github_tools import (
    execute_github_pending_action,
    handle_github_message,
)
from app.services.campus_agent.intent_v2 import route_mode_v2
from app.services.campus_agent.intent_router import route_intent, route_mode, should_override_current_mode
from app.services.campus_agent.learning_tools import handle_learning_message
from app.services.campus_agent.map_tools import (
    format_multi_mode_route,
    format_pois,
    format_route,
    format_transit_route,
    normalize_place_name,
    plan_multi_mode_route,
    plan_route,
    plan_transit_route,
    search_poi,
)
from app.services.campus_agent.memory import append_turn, recent_entities, recent_tool_context
from app.services.campus_agent.memory_service import AgentMemoryService
from app.services.campus_agent.pending_actions import (
    get_pending_action,
    is_action_expired,
    mark_action_cancelled,
    mark_action_executed,
    mark_action_expired,
    mark_action_failed,
    parse_action_args,
)
from app.services.campus_agent.planner import (
    CREATE_TOOL_CODES,
    is_capability_question,
    parse_confirmation,
)
from app.services.campus_agent.planning_graph import CampusAgentPlanningGraph
from app.services.campus_agent.registry import get_available_tools
from app.services.campus_agent.resolver import (
    CampusAgentResolver,
    TOOL_OBJECTS,
    draft_payload_from_tool_result,
    should_finish_draft,
    should_store_draft,
)
from app.services.campus_agent.schemas import AgentResponse
from app.services.campus_agent.sub_agents import (
    AcademicRelationAgent,
    HandlerSubAgent,
    MasterAgentRouter,
    SubAgentContext,
)
from app.services.campus_agent.task_drafts import (
    get_active_draft,
    mark_draft_cancelled,
    mark_draft_completed,
    upsert_task_draft,
)
from app.services.campus_agent.topic_qa_tools import handle_ai_knowledge_message, handle_worldcup_message
from app.services.campus_agent.tool_handlers import normalize_args
from app.services.campus_agent.web_search_tools import summarize_search_results


def format_available_tools(tools: list[dict]) -> str:
    if not tools:
        return "你当前账号暂时没有可通过足球助手调用的系统工具。"
    query_names = []
    write_names = []
    send_names = []
    for tool in tools:
        name = tool.get("name") or tool.get("code")
        if tool.get("action") == "query":
            query_names.append(name)
        elif tool.get("action") == "send":
            send_names.append(name)
        else:
            write_names.append(name)
    lines = ["你可以直接用自然语言让我在权限范围内查询和操作系统数据。"]
    if query_names:
        lines.append(f"可查询：{'、'.join(query_names[:12])}。")
    if write_names:
        lines.append(f"可新增/修改/停用：{'、'.join(write_names[:12])}。")
    if send_names:
        lines.append(f"可发送：{'、'.join(send_names[:8])}。")
    lines.append("你可以说：查询所有学生、张芳的性别是什么、林华的性别改为男、给学生吴浩发邮件。")
    lines.append("新增、修改、删除、群发邮件等敏感操作会先生成确认动作，确认后才真正执行。")
    return "\n".join(lines)


def format_unmatched_reply(*, previous_context: dict | None = None) -> str:
    if previous_context and previous_context.get("tool_code"):
        return "我还没完全理解这句话。你可以继续补充上一轮操作缺少的信息，或者换成更明确的说法，比如“全部显示”“选第一个”“主题是…内容是…”。"
    return "我还没抓准你想查什么或操作什么。你可以直接说“查询所有学生”“删除教师张伟”“查询北京天气”这类完整任务。"


def detect_auto_mode(message: str, conversation: Conversation | None = None) -> str | None:
    return route_mode_v2(message) or route_mode(message, conversation=conversation)


def detect_capability_override(message: str, current_mode: str, conversation: Conversation | None = None) -> str | None:
    """Allow explicit non-academic intents to escape a stale manually selected mode."""
    route = route_intent(message, conversation=conversation)
    return route.mode if should_override_current_mode(current_mode, route) else None


TASK_DRAFT_TOOL_CODES = {"send_email", "send_bulk_email", *CREATE_TOOL_CODES, *TOOL_OBJECTS.keys()}
ACADEMIC_DRAFT_MODES = {"auto", "academic_ops", "academic_tools"}


def _has_active_task_draft(memory_context) -> bool:
    draft = getattr(memory_context, "active_draft", None) if memory_context else None
    return bool(draft and draft.get("tool_code") in TASK_DRAFT_TOOL_CODES)


def _should_resume_academic_draft(memory_context, mode: str, message: str) -> bool:
    if message in {"取消", "放弃"}:
        return False
    if mode not in ACADEMIC_DRAFT_MODES:
        return False
    explicit_mode = route_mode_v2(message)
    if explicit_mode and explicit_mode != "academic_ops":
        return False
    return mode in ACADEMIC_DRAFT_MODES and _has_active_task_draft(memory_context)


def _format_rag_references(sources: list[dict]) -> list[dict]:
    refs = []
    for item in sources or []:
        refs.append({
            "id": item.get("chunk_id"),
            "title": item.get("title") or f"文档 {item.get('document_id')}",
            "content": "",
            "score": item.get("score") or 0,
            "metadata": {
                "kb_id": item.get("kb_id"),
                "document_id": item.get("document_id"),
                "chunk_no": item.get("chunk_no"),
                "vector_score": item.get("vector_score"),
                "bm25_score": item.get("bm25_score"),
                "title_score": item.get("title_score"),
            },
        })
    return refs


def _parse_route_message(text: str) -> tuple[str | None, str | None, str | None]:
    cleaned = (text or "").strip(" ，,。?？")
    for tail in ["怎么走", "的路线", "的线路", "路线", "如何去", "怎么去", "线路", "规划一下", "规划"]:
        cleaned = cleaned.replace(tail, "")
    waypoint = None
    for sep in ["途经", "经过", "中间地", "中途经过", "路过"]:
        if sep in cleaned:
            cleaned, waypoint = cleaned.split(sep, 1)
            waypoint = waypoint.strip(" ，,。?？")
            break

    chain = re.search(r"从(?P<origin>.+?)到(?P<middle>.+?)(?:再到|然后到|再去|然后去)(?P<dest>.+)$", cleaned)
    if chain:
        return (
            normalize_place_name(chain.group("origin").strip(" ，,。?？")),
            normalize_place_name(chain.group("dest").strip(" ，,。?？")),
            normalize_place_name(chain.group("middle").strip(" ，,。?？")),
        )

    patterns = [
        r"从(?P<origin>.+?)到(?P<dest>.+?)$",
        r"(?P<origin>.+?)到(?P<dest>.+?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            origin = match.group("origin").strip(" ，,。?？")
            destination = match.group("dest").strip(" ，,。?？")
            if destination.endswith("的"):
                destination = destination[:-1].strip(" ，,。?？")
            if origin and destination:
                return normalize_place_name(origin), normalize_place_name(destination), normalize_place_name(waypoint) if waypoint else None
    return None, None, waypoint


def _parse_poi_message(text: str) -> tuple[str, str | None]:
    keyword = "餐厅"
    for candidate in ["餐厅", "饭店", "咖啡", "奶茶", "超市", "景点", "商场", "酒店", "医院", "药店", "电影院", "吃喝玩乐"]:
        if candidate in text:
            keyword = "餐厅|咖啡|景点|商场" if candidate == "吃喝玩乐" else ("餐厅" if candidate == "饭店" else candidate)
            break

    location_name = text
    for word in ["附近", "周边", "搜索", "找", "有什么", "推荐", "的", "一下"]:
        location_name = location_name.replace(word, " ")
    for part in keyword.split("|"):
        location_name = location_name.replace(part, " ")
    location_name = " ".join(location_name.split()).strip(" ，,。?？")
    return keyword, location_name or None


def _route_preference(text: str) -> str:
    transit_words = [
        "公交",
        "公共交通",
        "坐车",
        "换乘",
        "坐地铁",
        "乘地铁",
        "搭地铁",
        "地铁路线",
        "优先地铁",
        "少换乘",
    ]
    if any(word in text for word in transit_words):
        return "transit"
    if any(word in text for word in ["自驾", "开车", "驾车", "打车"]):
        return "driving"
    return "multi"


def _recent_user_context(conversation: Conversation | None, limit: int = 4) -> list[str]:
    if not conversation or not isinstance(conversation.messages, list):
        return []
    items = []
    for msg in reversed(conversation.messages):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if content:
            items.append(content)
        if len(items) >= limit:
            break
    return list(reversed(items))


def _teacher_label(item: dict) -> str:
    relation = item.get("relation") or item.get("course_name") or "老师"
    name = item.get("name") or item.get("real_name") or item.get("username") or "未知"
    employee_no = f"，工号：{item.get('employee_no')}" if item.get("employee_no") else ""
    email = f"，邮箱：{item.get('email')}" if item.get("email") else ""
    return f"{relation}：{name}{employee_no}{email}"


def _message_refers_to_context_teacher(message: str) -> bool:
    text = re.sub(r"\s+", "", message or "")
    return any(word in text for word in ["老师", "教师", "任课老师", "班主任", "辅导员", "他们", "她们", "他", "她", "这个老师", "这些老师"])


def _teacher_email_args_from_context(message: str, conversation: Conversation | None) -> tuple[dict, str | None]:
    if not _message_refers_to_context_teacher(message):
        return {}, None
    teachers = recent_entities(conversation).get("teachers") or []
    teachers = [item for item in teachers if item.get("email") or item.get("user_id") or item.get("employee_no") or item.get("name")]
    if not teachers:
        return {}, "我知道你想联系老师，但当前会话里还没有可复用的老师信息。你可以先问“我的老师是谁”，或直接说“给李娜老师发邮件”。"

    text = message or ""
    preferred = []
    if "班主任" in text or "辅导员" in text:
        preferred = [item for item in teachers if "班主任" in str(item.get("relation") or "") or "辅导员" in str(item.get("relation") or "")]
    elif "任课" in text:
        preferred = [item for item in teachers if item.get("course_name") or item.get("relation") not in {"班主任/辅导员"}]
    else:
        for item in teachers:
            if item.get("name") and item["name"] in text:
                preferred = [item]
                break
            if item.get("course_name") and item["course_name"] in text:
                preferred = [item]
                break
    if preferred:
        teachers = preferred

    if len(teachers) > 1:
        lines = ["我找到了多位老师，请说明发给哪一位，或直接说“给所有任课老师发邮件”："]
        for idx, item in enumerate(teachers[:8], start=1):
            lines.append(f"{idx}. {_teacher_label(item)}")
        return {}, "\n".join(lines)

    teacher = teachers[0]
    args = {}
    if teacher.get("email"):
        args["recipient_email"] = teacher["email"]
    if teacher.get("user_id"):
        args["recipient_user_id"] = teacher["user_id"]
    args["recipient_keyword"] = teacher.get("name") or teacher.get("employee_no") or "老师"
    return args, None


def _format_teacher_course_followup(conversation: Conversation | None) -> str | None:
    courses = recent_entities(conversation).get("courses") or []
    pairs = []
    for item in courses:
        teacher = item.get("teacher") if isinstance(item.get("teacher"), dict) else {}
        course_name = item.get("course_name") or item.get("name")
        teacher_name = teacher.get("name") or item.get("teacher_name")
        if course_name and teacher_name:
            pairs.append((course_name, teacher_name))
    if not pairs:
        return None
    lines = ["根据上一轮查到的老师信息，他们对应的课程是："]
    seen = set()
    for course_name, teacher_name in pairs[:20]:
        key = (course_name, teacher_name)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {teacher_name}：{course_name}")
    return "\n".join(lines)


def _needs_context_completion(tool_code: str, args: dict, message: str) -> bool:
    if tool_code == "send_email":
        if not _message_refers_to_context_teacher(message):
            return False
        if args.get("recipient_email") or args.get("recipient_user_id"):
            return False
        keyword = (args.get("recipient_keyword") or "").strip()
        return not keyword or keyword in {"老师", "教师", "任课老师", "班主任", "辅导员", "他们", "她们", "他", "她"}
    return False


class CampusAgentOrchestrator:
    """Coordinates planning, memory, permissions, execution and replies."""

    def __init__(self, db: Session):
        self.db = db
        self.planning_graph = CampusAgentPlanningGraph()
        self.resolver = CampusAgentResolver()
        self.executor = CampusAgentExecutor(db)
        self.memory_service = AgentMemoryService(db)
        self.runtime = build_default_runtime()
        self.master_agent = self._build_master_agent()

    def _build_master_agent(self) -> MasterAgentRouter:
        def academic_execute(tool_code: str, args: dict, ctx: SubAgentContext) -> AgentResponse:
            return self._execute_plan(
                user=ctx.user,
                conversation=ctx.conversation,
                session_id=ctx.session_id,
                message=ctx.message,
                mode=ctx.mode,
                tool_code=tool_code,
                args=args,
                response_mode="academic_ops",
            )

        return MasterAgentRouter([
            AcademicRelationAgent(self.db, academic_execute),
            HandlerSubAgent(
                "rag",
                "RAG知识库子Agent",
                {"rag"},
                lambda ctx: self._answer_with_knowledge_base(
                    user=ctx.user,
                    conversation=ctx.conversation,
                    session_id=ctx.session_id,
                    message=ctx.message,
                    mode=ctx.mode,
                ),
            ),
            HandlerSubAgent(
                "search",
                "搜索子Agent",
                {"search"},
                lambda ctx: self._handle_search(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
            HandlerSubAgent(
                "github",
                "GitHub子Agent",
                {"github"},
                lambda ctx: self._handle_github(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
            HandlerSubAgent(
                "code_review",
                "编程助手子Agent",
                {"code_review"},
                lambda ctx: self._handle_code_review(
                    user=ctx.user,
                    conversation=ctx.conversation,
                    session_id=ctx.session_id,
                    message=ctx.message,
                    llm_provider=ctx.llm_provider,
                    llm_model=ctx.llm_model,
                ),
            ),
            HandlerSubAgent(
                "document",
                "文档处理子Agent",
                {"document"},
                lambda ctx: self._handle_document(
                    user=ctx.user,
                    conversation=ctx.conversation,
                    session_id=ctx.session_id,
                    message=ctx.message,
                    file_ids=ctx.file_ids or [],
                ),
            ),
            HandlerSubAgent(
                "emotion",
                "情绪陪伴子Agent",
                {"emotion"},
                lambda ctx: self._handle_emotion(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
            HandlerSubAgent(
                "study",
                "学习辅导子Agent",
                {"study"},
                lambda ctx: self._handle_learning(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
            HandlerSubAgent(
                "map",
                "路线生活子Agent",
                {"map", "life"},
                lambda ctx: self._handle_map(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message, mode=ctx.mode),
            ),
            HandlerSubAgent(
                "data_analysis",
                "数据分析子Agent",
                {"data_analysis"},
                lambda ctx: self._handle_data_analysis(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
            HandlerSubAgent(
                "worldcup",
                "世界杯问答子Agent",
                {"worldcup"},
                lambda ctx: self._handle_worldcup(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
            HandlerSubAgent(
                "ai_knowledge",
                "AI知识问答子Agent",
                {"ai_knowledge"},
                lambda ctx: self._handle_ai_knowledge(user=ctx.user, conversation=ctx.conversation, session_id=ctx.session_id, message=ctx.message),
            ),
        ])

    def chat(
        self,
        *,
        user: User,
        conversation: Conversation,
        session_id: str,
        message: str,
        mode: str,
        file_ids: list[str] | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> AgentResponse:
        message = message.strip()
        memory_context = self.memory_service.load_context(
            user=user,
            conversation=conversation,
            session_id=session_id,
            module_code="campus_agent",
        )
        confirmation = parse_confirmation(message)
        if confirmation:
            return self._handle_confirmation(
                user=user,
                conversation=conversation,
                session_id=session_id,
                message=message,
                mode=mode,
                confirmation=confirmation,
            )

        if file_ids and mode == "auto":
            mode = "document"
        elif _should_resume_academic_draft(memory_context, mode, message):
            mode = "academic_ops"
        if mode == "auto":
            detected_mode = route_mode_v2(message) or route_mode(
                message,
                conversation=conversation,
                memory_context=memory_context,
            )
            if detected_mode:
                mode = detected_mode
        delegated = self.master_agent.dispatch(SubAgentContext(
            user=user,
            conversation=conversation,
            session_id=session_id,
            message=message,
            mode=mode,
            memory_context=memory_context,
            file_ids=file_ids or [],
            llm_provider=llm_provider,
            llm_model=llm_model,
        ))
        if delegated:
            return delegated

        available_tools = get_available_tools(user, self.db)
        if is_capability_question(message):
            reply = format_available_tools(available_tools)
            append_turn(
                self.db,
                conversation,
                user_message=message,
                assistant_reply=reply,
                mode="academic_ops" if mode == "auto" else mode,
                intent="list_available_tools",
            )
            return AgentResponse(
                reply=reply,
                mode="academic_ops" if mode == "auto" else mode,
                intent="list_available_tools",
                suggested_mode="academic_ops",
            )

        if mode in {"academic_tools", "academic_ops"} and message.startswith("/tool "):
            return self._handle_tool_check(
                user=user,
                conversation=conversation,
                message=message,
                mode=mode,
            )

        available_tool_codes = {tool["code"] for tool in available_tools}
        plan = self.planning_graph.plan(
            message,
            mode=mode,
            available_tool_codes=available_tool_codes,
            memory_context=memory_context,
        )
        plan = self.resolver.resolve(plan, message, memory_context)

        if not plan.tool_code:
            previous_context = memory_context.active_draft or memory_context.last_tool
            reply = format_unmatched_reply(previous_context=previous_context)
            append_turn(
                self.db,
                conversation,
                user_message=message,
                assistant_reply=reply,
                mode=mode,
                intent="campus_agent_unmatched",
            )
            return AgentResponse(reply=reply, mode=mode, intent="campus_agent_unmatched")

        return self._execute_plan(
            user=user,
            conversation=conversation,
            session_id=session_id,
            message=message,
            mode=mode,
            tool_code=plan.tool_code,
            args=plan.args,
            response_mode=plan.response_mode,
        )

    def _execute_plan(
        self,
        *,
        user: User,
        conversation: Conversation,
        session_id: str,
        message: str,
        mode: str,
        tool_code: str,
        args: dict,
        response_mode: str,
    ) -> AgentResponse:
        if tool_code == "query_my_teachers" and args.get("_relation_followup") == "teacher_courses":
            reply = _format_teacher_course_followup(conversation)
            if reply:
                append_turn(
                    self.db,
                    conversation,
                    user_message=message,
                    assistant_reply=reply,
                    mode=response_mode,
                    intent="query_my_teacher_courses_followup",
                    tool_code="query_my_teachers",
                    tool_args=args,
                    tool_status="success",
                    tool_data={"followup": "teacher_courses", "items": recent_entities(conversation).get("courses") or []},
                )
                return AgentResponse(
                    reply=reply,
                    mode=response_mode,
                    intent="query_my_teacher_courses_followup",
                    suggested_mode=response_mode,
                )
            args = {k: v for k, v in args.items() if k != "_relation_followup"}

        active_draft = get_active_draft(self.db, user=user, session_id=session_id)
        if active_draft and active_draft.tool_code != tool_code:
            mark_draft_cancelled(self.db, active_draft)
            active_draft = None
        tool_args = normalize_args(tool_code, message, args)
        if _needs_context_completion(tool_code, tool_args, message):
            context_args, clarify = _teacher_email_args_from_context(message, conversation)
            if clarify:
                append_turn(
                    self.db,
                    conversation,
                    user_message=message,
                    assistant_reply=clarify,
                    mode=response_mode,
                    intent="context_reference_clarify",
                    tool_code=tool_code,
                    tool_args=tool_args,
                    tool_status="need_more_info",
                    tool_data={"missing_fields": ["收件人"], "teachers": recent_entities(conversation).get("teachers") or []},
                )
                return AgentResponse(reply=clarify, mode=response_mode, intent="context_reference_clarify", suggested_mode=response_mode)
            tool_args = {**tool_args, **context_args}
        tool_result = self.executor.execute(user, tool_code, tool_args, session_id=session_id)

        if tool_result.data and isinstance(tool_result.data, dict) and tool_result.data.get("pending_action_id"):
            tool_args["pending_action_id"] = tool_result.data.get("pending_action_id")

        if should_store_draft(tool_code, tool_result):
            missing_fields, candidates = draft_payload_from_tool_result(tool_result)
            draft = upsert_task_draft(
                self.db,
                user=user,
                session_id=session_id,
                mode=response_mode,
                tool_code=tool_code,
                args=tool_args,
                missing_fields=missing_fields,
                candidates=candidates,
                message=tool_result.message,
            )
            tool_args["draft_id"] = draft.id
        elif should_finish_draft(tool_result):
            if active_draft and active_draft.tool_code == tool_code:
                mark_draft_completed(self.db, active_draft)

        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=tool_result.message,
            mode=response_mode,
            intent=tool_code,
            tool_code=tool_code,
            tool_args=tool_args,
            tool_status=tool_result.status,
            tool_data=tool_result.data if isinstance(tool_result.data, dict) else {},
        )
        self._remember_tool_event(
            user=user,
            tool_code=tool_code,
            message=message,
            tool_result=tool_result,
        )
        return AgentResponse(
            reply=tool_result.message,
            mode=response_mode,
            intent=tool_code,
            tool_calls=[tool_result.to_dict()],
            suggested_mode=response_mode,
        )

    def _handle_confirmation(
        self,
        *,
        user: User,
        conversation: Conversation,
        session_id: str,
        message: str,
        mode: str,
        confirmation: tuple[str, int],
    ) -> AgentResponse:
        action_word, action_id = confirmation
        if not action_id:
            memory_context = self.memory_service.load_context(user=user, conversation=conversation, session_id=session_id)
            previous_context = memory_context.last_tool or {}
            tool_args = previous_context.get("tool_args") or {}
            action_id = int(tool_args.get("pending_action_id") or 0)

        action = get_pending_action(self.db, action_id, user) if action_id else None
        if not action:
            reply = "没有找到可确认的待执行动作。请带上待确认动作 ID，例如：确认 12。"
            append_turn(self.db, conversation, user_message=message, assistant_reply=reply, mode=mode, intent="confirm_action_missing")
            return AgentResponse(reply=reply, mode=mode, intent="confirm_action_missing")

        if action_word in {"取消", "放弃"}:
            mark_action_cancelled(self.db, action)
            active_draft = get_active_draft(self.db, user=user, session_id=session_id)
            if active_draft and active_draft.tool_code == action.tool_code:
                mark_draft_cancelled(self.db, active_draft)
            reply = f"已取消待确认动作 {action.id}。"
            append_turn(self.db, conversation, user_message=message, assistant_reply=reply, mode=mode, intent="cancel_pending_action")
            return AgentResponse(reply=reply, mode=mode, intent="cancel_pending_action")

        if action.status != "pending":
            reply = f"动作 {action.id} 当前状态是 {action.status}，不能重复确认。"
            append_turn(self.db, conversation, user_message=message, assistant_reply=reply, mode=mode, intent="confirm_action_invalid")
            return AgentResponse(reply=reply, mode=mode, intent="confirm_action_invalid")

        if is_action_expired(action):
            mark_action_expired(self.db, action)
            reply = f"动作 {action.id} 已过期，请重新发起操作。"
            append_turn(self.db, conversation, user_message=message, assistant_reply=reply, mode=mode, intent="confirm_action_expired")
            return AgentResponse(reply=reply, mode=mode, intent="confirm_action_expired")

        tool_args = parse_action_args(action)
        if action.tool_code == "emotion_care_email":
            tool_result = self._execute_emotion_care_email(user, tool_args)
        elif action.tool_code == "github_create_issue":
            tool_result = self._execute_github_pending_action(tool_args)
        else:
            tool_result = self.executor.execute(user, action.tool_code, tool_args, confirmed=True, session_id=session_id)
        if tool_result.success:
            mark_action_executed(self.db, action, tool_result.to_dict())
            active_draft = get_active_draft(self.db, user=user, session_id=session_id)
            if active_draft and active_draft.tool_code == action.tool_code:
                mark_draft_completed(self.db, active_draft)
        else:
            mark_action_failed(self.db, action, tool_result.message)

        response_mode = "github" if action.tool_code.startswith("github_") else "academic_ops"
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=tool_result.message,
            mode=response_mode,
            intent=f"confirm_{action.tool_code}",
            tool_code=action.tool_code,
            tool_args={"pending_action_id": action.id},
            tool_status=tool_result.status,
            tool_data=tool_result.data if isinstance(tool_result.data, dict) else {},
        )
        self._remember_tool_event(
            user=user,
            tool_code=action.tool_code,
            message=f"确认动作 {action.id}",
            tool_result=tool_result,
        )
        return AgentResponse(
            reply=tool_result.message,
            mode=response_mode,
            intent=f"confirm_{action.tool_code}",
            tool_calls=[tool_result.to_dict()],
            suggested_mode=response_mode,
        )

    def _remember_tool_event(self, *, user: User, tool_code: str, message: str, tool_result) -> None:
        if not getattr(tool_result, "success", False):
            return
        try:
            self.memory_service.remember_event(
                user=user,
                module_code="campus_agent",
                event_type="tool_success",
                content=f"{tool_code}: {message}",
                payload={
                    "tool_code": tool_code,
                    "status": getattr(tool_result, "status", None),
                    "data": getattr(tool_result, "data", {}) if isinstance(getattr(tool_result, "data", {}), dict) else {},
                    "importance": 2 if tool_code.startswith(("create_", "update_", "delete_", "send_")) else 1,
                },
            )
        except Exception:
            return

    def _execute_github_pending_action(self, args: dict):
        class _Result:
            def __init__(self, success: bool, message: str, data: dict | None = None):
                self.success = success
                self.message = message
                self.tool = "github_create_issue"
                self.status = "success" if success else "failed"
                self.data = data or {}
                self.confirm_required = False
                self.risk = "medium"

            def to_dict(self):
                return {
                    "tool": self.tool,
                    "status": self.status,
                    "success": self.success,
                    "message": self.message,
                    "data": self.data,
                    "confirm_required": False,
                    "risk": self.risk,
                }

        success, reply, data = execute_github_pending_action(args)
        return _Result(success, reply, data)

    def _execute_emotion_care_email(self, user: User, args: dict):
        class _Result:
            def __init__(self, success: bool, message: str, data: dict | None = None):
                self.success = success
                self.message = message
                self.tool = "emotion_care_email"
                self.status = "success" if success else "failed"
                self.data = data or {}
                self.confirm_required = False
                self.risk = "high"

            def to_dict(self):
                return {
                    "tool": self.tool,
                    "status": self.status,
                    "success": self.success,
                    "message": self.message,
                    "data": self.data,
                    "confirm_required": False,
                    "risk": self.risk,
                }

        sent = []
        try:
            for email in args.get("recipient_emails") or []:
                msg = email_service.send_email(
                    sender=user,
                    recipient_email=email,
                    subject=args.get("subject") or "学生情绪状态关注提醒",
                    body=args.get("body") or "",
                    attachments=None,
                    db=self.db,
                )
                sent.append({"id": msg.id, "email": email})
            return _Result(True, f"已发送关怀提醒给 {len(sent)} 位老师。", {"sent": sent})
        except Exception as exc:
            return _Result(False, f"关怀提醒发送失败：{exc}", {"sent": sent})

    def _handle_tool_check(
        self,
        *,
        user: User,
        conversation: Conversation,
        message: str,
        mode: str,
    ) -> AgentResponse:
        parts = message.split(maxsplit=2)
        tool_code = parts[1] if len(parts) > 1 else ""
        tool_result = self.executor.execute(user, tool_code)
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=tool_result.message,
            mode=mode,
            intent="tool_access_check",
            tool_code=tool_code,
            tool_args={},
            tool_status=tool_result.status,
        )
        return AgentResponse(
            reply=tool_result.message,
            mode=mode,
            intent="tool_access_check",
            tool_calls=[tool_result.to_dict()],
        )

    def _answer_with_knowledge_base(
        self,
        *,
        user: User,
        conversation: Conversation,
        session_id: str,
        message: str,
        mode: str,
    ) -> AgentResponse:
        result = rag_knowledge_service.answer(
            db=self.db,
            user=user,
            question=message,
            kb_ids=None,
            top_k=5,
            min_score=0,
        )
        reply = result.get("answer") or "我没有在当前可访问的知识库中检索到足够相关的内容。"
        references = _format_rag_references(result.get("sources") or [])
        if not references:
            reply = (
                "我还没有在你的综合知识库里找到可引用的资料。\n"
                "你可以先进入“综合知识库”页面，新建知识库并导入文本、Markdown 或 PDF，然后再回来问我。"
            )
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="rag",
            intent="rag_knowledge_ask",
            tool_data={
                "references": references,
                "kb_ids": result.get("kb_ids") or [],
                "retrieval": result.get("retrieval") or {},
            },
        )
        return AgentResponse(
            reply=reply,
            mode="rag",
            intent="rag_knowledge_ask",
            references=references,
            suggested_mode="rag",
        )

    def _handle_document(
        self,
        *,
        user: User,
        conversation: Conversation,
        session_id: str,
        message: str,
        file_ids: list[str] | None = None,
    ) -> AgentResponse:
        files = []
        for file_id in file_ids or []:
            try:
                files.append(resolve_agent_file(user, file_id))
            except Exception:
                continue
        previous_file_context = []
        recent_tool = recent_tool_context(conversation, {"document_ocr", "document_summarize", "document_translate", "document_save_to_kb"})
        if recent_tool:
            previous_file_context = (recent_tool.get("tool_data") or {}).get("files") or []
        reply, data = handle_document_message(
            message,
            user=user,
            db=self.db,
            files=files,
            previous_file_context=previous_file_context,
        )
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="document",
            intent=f"document_{data.get('task', 'process')}",
            tool_code=f"document_{data.get('task', 'process')}",
            tool_status="success" if not data.get("errors") else "partial",
            tool_data=data,
        )
        return AgentResponse(reply=reply, mode="document", intent=f"document_{data.get('task', 'process')}", suggested_mode="document")

    def _handle_code_review(
        self,
        *,
        user: User,
        conversation: Conversation,
        session_id: str,
        message: str,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> AgentResponse:
        previous_index = None
        recent_tool = recent_tool_context(conversation, {"code_analysis", "coding_assistant"})
        if recent_tool:
            previous_index = (recent_tool.get("tool_data") or {}).get("index")
        try:
            if _looks_like_project_analysis(message):
                reply, data = analyze_code_message(
                    message,
                    previous_index=previous_index,
                    user_id=user.id,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
            else:
                reply, data = handle_coding_assistant_message(
                    message,
                    previous_index=previous_index,
                    user_id=user.id,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
        except Exception as exc:
            reply = f"编程助手处理失败：{exc}"
            data = {"task": "coding_assistant", "error": str(exc)}
        task_name = data.get("task") or "coding_assistant"
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="code_review",
            intent=task_name,
            tool_code=task_name,
            tool_status="failed" if data.get("error") else "success",
            tool_data=data,
        )
        return AgentResponse(reply=reply, mode="code_review", intent=task_name, suggested_mode="code_review")

    def _handle_search(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        previous_results = []
        recent_tool = recent_tool_context(conversation, {"web_search"})
        if recent_tool:
            previous_results = (recent_tool.get("tool_data") or {}).get("results") or []
        if previous_results and any(marker in message for marker in ["第二条", "第2条", "第一条", "第1条", "第三条", "第3条", "详细说说", "展开", "总结成表格"]):
            data = {"query": f"基于上一轮搜索结果追问：{message}", "results": previous_results, "provider": "memory"}
            reply = summarize_search_results(data["query"], previous_results)
        else:
            data = self.runtime.mcp.invoke("web_search", {"query": message, "limit": 6, "fresh": True})
            results = data.get("results") or []
            summary_query = data.get("original_query") or message
            reply = summarize_search_results(summary_query, results) if data.get("ok") else (data.get("error") or "联网搜索暂时不可用。")
        references = []
        for idx, item in enumerate(data.get("results") or [], 1):
            references.append({
                "id": idx,
                "title": item.get("title") or item.get("source") or f"搜索结果 {idx}",
                "content": item.get("snippet") or item.get("url") or "",
                "score": 1,
                "metadata": {
                    "url": item.get("url"),
                    "source": item.get("source"),
                    "published_at": item.get("published_at"),
                },
            })
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="search",
            intent="web_search",
            tool_code="web_search",
            tool_args={"query": message, "fresh": True},
            tool_status="success" if data.get("results") else "failed",
            tool_data=data,
        )
        return AgentResponse(
            reply=reply,
            mode="search",
            intent="web_search",
            references=references,
            suggested_mode="search",
            tool_calls=[{
                "tool": "web_search",
                "status": "success" if data.get("results") else "failed",
                "success": bool(data.get("results")),
                "message": data.get("error") or "联网搜索完成",
                "data": data,
            }],
        )

    def _handle_github(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        previous_context = recent_tool_context(conversation, {"github", "github_create_issue"})
        reply, data = handle_github_message(
            db=self.db,
            user=user,
            session_id=session_id,
            message=message,
            previous_context=previous_context,
        )
        status = "confirm_required" if data.get("pending_action_id") else ("failed" if data.get("error") else "success")
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="github",
            intent=f"github_{data.get('task', 'process')}",
            tool_code="github_create_issue" if data.get("pending_action_id") else "github",
            tool_args={"pending_action_id": data.get("pending_action_id")} if data.get("pending_action_id") else {},
            tool_status=status,
            tool_data=data,
        )
        return AgentResponse(
            reply=reply,
            mode="github",
            intent=f"github_{data.get('task', 'process')}",
            suggested_mode="github",
            tool_calls=[{
                "tool": "github",
                "status": status,
                "success": not data.get("error"),
                "message": reply,
                "data": data,
            }],
        )

    def _handle_emotion(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        context_messages = _recent_user_context(conversation)
        reply, data = handle_emotion_message(user, self.db, session_id, message, context_messages=context_messages)
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="emotion",
            intent="emotion_companion",
            tool_data=data,
            tool_code="emotion_care_email" if data.get("pending_action_id") else None,
            tool_args={"pending_action_id": data.get("pending_action_id")} if data.get("pending_action_id") else {},
            tool_status="confirm_required" if data.get("pending_action_id") else "success",
        )
        return AgentResponse(reply=reply, mode="emotion", intent="emotion_companion", suggested_mode="emotion")

    def _handle_learning(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        context_messages = _recent_user_context(conversation)
        reply, data, references = handle_learning_message(
            user=user,
            db=self.db,
            message=message,
            context_messages=context_messages,
        )
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="study",
            intent=f"learning_{data.get('intent', 'general_learning')}",
            tool_code="learning_tutor",
            tool_status="success",
            tool_data=data,
        )
        return AgentResponse(
            reply=reply,
            mode="study",
            intent=f"learning_{data.get('intent', 'general_learning')}",
            references=references,
            suggested_mode="study",
        )

    def _handle_data_analysis(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        reply, data = handle_data_analysis_message(user=user, db=self.db, message=message)
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="data_analysis",
            intent=f"data_analysis_{data.get('task', 'overview')}",
            tool_code="data_analysis",
            tool_status="success",
            tool_data=data,
        )
        return AgentResponse(
            reply=reply,
            mode="data_analysis",
            intent=f"data_analysis_{data.get('task', 'overview')}",
            suggested_mode="data_analysis",
            tool_calls=[{
                "tool": "data_analysis",
                "status": "success",
                "success": True,
                "message": "数据分析完成",
                "data": data,
            }],
        )

    def _handle_worldcup(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        context_messages = _recent_user_context(conversation)
        reply, data, references = handle_worldcup_message(
            user=user,
            db=self.db,
            message=message,
            context_messages=context_messages,
        )
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="worldcup",
            intent="worldcup_qa",
            tool_code="worldcup_qa",
            tool_status="success",
            tool_data=data,
        )
        return AgentResponse(reply=reply, mode="worldcup", intent="worldcup_qa", references=references, suggested_mode="worldcup")

    def _handle_ai_knowledge(self, *, user: User, conversation: Conversation, session_id: str, message: str) -> AgentResponse:
        context_messages = _recent_user_context(conversation)
        reply, data, references = handle_ai_knowledge_message(
            user=user,
            db=self.db,
            message=message,
            context_messages=context_messages,
        )
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode="ai_knowledge",
            intent="ai_knowledge_qa",
            tool_code="ai_knowledge_qa",
            tool_status="success",
            tool_data=data,
        )
        return AgentResponse(reply=reply, mode="ai_knowledge", intent="ai_knowledge_qa", references=references, suggested_mode="ai_knowledge")

    def _handle_map(self, *, user: User, conversation: Conversation, session_id: str, message: str, mode: str) -> AgentResponse:
        text = message.strip()
        if any(word in text for word in ["附近", "周边", "吃", "喝", "玩", "乐", "餐厅", "咖啡", "景点", "商场"]):
            keyword, location_name = _parse_poi_message(text)
            geo = None
            if location_name:
                from app.services.campus_agent.map_tools import geocode
                geo = geocode(location_name)
            pois = []
            if "|" in keyword:
                for item in keyword.split("|"):
                    pois.extend(search_poi(item, location=geo.get("location") if geo else None)[:3])
            else:
                pois = search_poi(keyword, location=geo.get("location") if geo else None)
            reply = format_pois(pois, keyword)
            data = {
                "keyword": keyword,
                "location": geo,
                "items": pois,
                "visual": {
                    "type": "poi",
                    "title": f"{location_name or '附近'} · {keyword}",
                    "keyword": keyword,
                    "location": geo,
                    "items": pois,
                },
            }
            intent = "map_poi_search"
        else:
            origin, destination, waypoint = _parse_route_message(text)
            if not origin or not destination:
                reply = "路线规划还缺少出发地或目的地。你可以这样说：从学校到火车站怎么走，或者从学校到机场途经市中心。"
                data = {"ok": False, "missing": ["origin", "destination"]}
                intent = "map_route_missing"
                append_turn(
                    self.db,
                    conversation,
                    user_message=message,
                    assistant_reply=reply,
                    mode=mode,
                    intent=intent,
                    tool_data=data,
                )
                return AgentResponse(reply=reply, mode=mode, intent=intent, suggested_mode=mode)
            preference = _route_preference(text)
            if preference == "transit":
                result = plan_transit_route(origin, destination, waypoint=waypoint)
                reply = format_transit_route(result)
                intent = "map_transit_route_plan"
            elif preference == "driving":
                result = plan_route(origin, destination, waypoint=waypoint)
                reply = format_route(result)
                intent = "map_driving_route_plan"
            else:
                result = plan_multi_mode_route(origin, destination, waypoint=waypoint)
                reply = format_multi_mode_route(result)
                intent = "map_multi_mode_route_plan"
            data = result
        append_turn(
            self.db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode=mode,
            intent=intent,
            tool_data=data if isinstance(data, dict) else {},
        )
        tool_calls = []
        if isinstance(data, dict) and data.get("visual"):
            tool_calls.append({"tool_code": intent, "status": "success" if data.get("ok", True) else "failed", "data": data})
        return AgentResponse(reply=reply, mode=mode, intent=intent, tool_calls=tool_calls, suggested_mode=mode)
