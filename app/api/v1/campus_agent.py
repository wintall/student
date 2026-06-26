"""
Campus AI assistant routes.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import ai_service
from app.services.campus_agent import CampusAgentExecutor, get_available_tools
from app.services.campus_agent.memory import append_turn, clear_session, get_or_create_session, last_tool_context
from app.services.campus_agent.tool_handlers import normalize_args
from app.utils.response import success

router = APIRouter(prefix="/campus-agent", tags=["校园助手"])


ASSISTANT_MODES = [
    {
        "code": "auto",
        "name": "自动",
        "description": "自动判断问题类型并选择合适能力",
        "quick_questions": ["我的课表", "我的成绩怎么样", "最近有什么公告"],
    },
    {
        "code": "rag",
        "name": "RAG知识问答",
        "description": "面向文学、制度、资料库的知识检索问答",
        "quick_questions": ["三打白骨精是哪一回", "帮我查一段名著知识"],
    },
    {
        "code": "academic_tools",
        "name": "教务查询",
        "description": "查询成绩、课表、请假、考勤、公告等系统数据",
        "quick_questions": ["查看我的考勤", "我的请假进度", "今天有什么课"],
    },
    {
        "code": "study",
        "name": "学习辅导",
        "description": "生成学习计划、复习建议和课程辅导思路",
        "quick_questions": ["帮我制定复习计划", "数学怎么查漏补缺"],
    },
    {
        "code": "document",
        "name": "文档处理",
        "description": "后续用于文档总结、提纲、重点提取",
        "quick_questions": ["帮我总结一份课程资料", "提取文档重点"],
    },
    {
        "code": "emotion",
        "name": "情绪陪伴",
        "description": "面向考试压力、学习焦虑和日常倾诉",
        "quick_questions": ["我最近考试压力很大", "帮我调整学习状态"],
    },
    {
        "code": "data_analysis",
        "name": "数据分析",
        "description": "面向数据体检、统计分析和管理建议",
        "quick_questions": ["系统还有哪些高危异常", "分析一下学生成绩趋势"],
    },
    {
        "code": "worldcup",
        "name": "世界杯问答",
        "description": "世界杯知识、球队、球星、赛制问答",
        "quick_questions": ["2022世界杯冠军是谁", "世界杯小组赛规则是什么"],
    },
    {
        "code": "ai_knowledge",
        "name": "AI知识问答",
        "description": "LangChain、LangGraph、FastAPI、Dify、Python、Linux、SQL等技术问答",
        "quick_questions": ["LangGraph和LangChain区别", "FastAPI常见面试题"],
    },
]


MODE_HINTS = {
    "rag": "当前处于 RAG 知识问答模式。第一版会先用通用助手响应，后续接入知识库检索和引用来源。",
    "academic_tools": "当前处于教务查询模式。你可以询问成绩、课表、请假、考勤和公告。",
    "study": "当前处于学习辅导模式。你可以让助手帮你拆解学习目标、制定计划或解释知识点。",
    "document": "当前处于文档处理模式。文件上传和文档解析会在后续迭代接入。",
    "emotion": "当前处于情绪陪伴模式。助手会以支持性、非诊断的方式回应你的压力和困扰。",
    "data_analysis": "当前处于数据分析模式。后续会接入数据体检、统计和趋势分析工具。",
    "worldcup": "当前处于世界杯问答模式。后续会接入世界杯知识库。",
    "ai_knowledge": "当前处于 AI 知识问答模式。后续会接入 AI 技术知识库和面试题库。",
}


class CampusAgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    mode: str = Field(default="auto")
    session_id: str | None = None


class CampusAgentClearRequest(BaseModel):
    session_id: str | None = None


def _mode_exists(mode: str) -> bool:
    return any(item["code"] == mode for item in ASSISTANT_MODES)


def _suggested_questions(mode: str) -> list[str]:
    for item in ASSISTANT_MODES:
        if item["code"] == mode:
            return item["quick_questions"]
    return ASSISTANT_MODES[0]["quick_questions"]


def _format_available_tools(tools: list[dict]) -> str:
    if not tools:
        return "你当前账号暂时没有可通过足球助手调用的系统工具。"
    lines = ["你当前可以通过足球助手使用这些系统工具：", ""]
    for tool in tools:
        confirm_text = "，需要确认" if tool.get("confirm_required") else ""
        lines.append(
            f"- {tool['name']}（{tool['code']}）：{tool['description']} "
            f"权限码：{tool['permission']}，风险：{tool['risk']}{confirm_text}"
        )
    lines.append("")
    lines.append("第一步已完成工具白名单和权限映射。下一步会把这些工具逐个接入真实查询和业务操作。")
    return "\n".join(lines)


def _is_tool_capability_question(message: str) -> bool:
    keywords = [
        "你能做什么",
        "可以做什么",
        "能操作什么",
        "有哪些工具",
        "工具清单",
        "权限内",
        "我的权限",
        "能查什么",
    ]
    return any(keyword in message for keyword in keywords)


def _detect_academic_tool(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    if any(word in text for word in ["课表", "课程表", "今天有什么课", "明天有什么课", "在哪上课", "上什么课"]):
        return "query_my_schedule"
    if any(word in text for word in ["考勤", "出勤", "缺勤", "迟到", "早退"]):
        return "query_my_attendance"
    if any(word in text for word in ["我的请假", "请假进度", "请假申请", "请假状态"]):
        return "query_my_leave"
    if any(word in text for word in ["公告", "通知", "校园通知", "最新消息"]):
        return "query_announcements"
    return None


def _detect_followup_tool(message: str, previous_tool: str | None) -> str | None:
    if not previous_tool:
        return None
    text = (message or "").strip()
    if not text:
        return None
    followup_words = ["那", "再", "只看", "筛选", "换成", "今天", "明天", "上一条", "详细", "继续"]
    if not any(word in text for word in followup_words):
        return None
    if previous_tool == "query_my_schedule" and any(word in text for word in ["今天", "明天", "课", "上课", "那"]):
        return previous_tool
    if previous_tool == "query_my_attendance" and any(word in text for word in ["请假", "迟到", "缺勤", "考勤", "只看", "那"]):
        return previous_tool
    if previous_tool == "query_my_leave" and any(word in text for word in ["待审批", "通过", "驳回", "请假", "那", "只看"]):
        return previous_tool
    if previous_tool == "query_announcements" and any(word in text for word in ["公告", "通知", "再", "上一条", "详细"]):
        return previous_tool
    return None


def _chat_response(
    *,
    session_id: str,
    reply: str,
    mode: str,
    intent: str,
    tool_calls: list,
    suggested_mode: str | None = None,
):
    return success(data={
        "session_id": session_id,
        "reply": reply,
        "mode": mode,
        "intent": intent,
        "tool_calls": tool_calls,
        "references": [],
        "suggested_questions": _suggested_questions(suggested_mode or mode),
    })


@router.get("/modes")
def list_modes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = []
    available_tools = get_available_tools(user, db)
    for mode in ASSISTANT_MODES:
        item = dict(mode)
        if mode["code"] == "academic_tools":
            item["tools"] = available_tools
        data.append(item)
    return success(data=data)


@router.get("/tools")
def list_tools(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(data=get_available_tools(user, db))


@router.post("/clear")
def clear_chat(
    body: CampusAgentClearRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.session_id:
        _, conversation = get_or_create_session(db, body.session_id, user)
        clear_session(db, conversation)
    return success(message="校园助手对话已清空")


@router.post("/chat")
def chat(
    body: CampusAgentChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mode = body.mode if _mode_exists(body.mode) else "auto"
    session_id, conversation = get_or_create_session(db, body.session_id, user)

    message = body.message.strip()
    available_tools = get_available_tools(user, db)

    if mode == "academic_tools" and _is_tool_capability_question(message):
        reply = _format_available_tools(available_tools)
        append_turn(
            db,
            conversation,
            user_message=message,
            assistant_reply=reply,
            mode=mode,
            intent="list_available_tools",
        )
        return _chat_response(
            session_id=session_id,
            reply=reply,
            mode=mode,
            intent="list_available_tools",
            tool_calls=[],
        )

    if mode == "academic_tools" and message.startswith("/tool "):
        parts = message.split(maxsplit=2)
        tool_code = parts[1] if len(parts) > 1 else ""
        executor = CampusAgentExecutor(db)
        tool_result = executor.execute(user, tool_code)
        append_turn(
            db,
            conversation,
            user_message=message,
            assistant_reply=tool_result.message,
            mode=mode,
            intent="tool_access_check",
            tool_code=tool_code,
            tool_args={},
            tool_status=tool_result.status,
        )
        return _chat_response(
            session_id=session_id,
            reply=tool_result.message,
            mode=mode,
            intent="tool_access_check",
            tool_calls=[tool_result.to_dict()],
        )

    previous_context = last_tool_context(conversation)
    explicit_tool = _detect_academic_tool(message) if mode in {"auto", "academic_tools"} else None
    followup_tool = _detect_followup_tool(message, previous_context.get("tool_code") if previous_context else None)
    detected_tool = explicit_tool or followup_tool
    if detected_tool:
        executor = CampusAgentExecutor(db)
        tool_args = {}
        if followup_tool and previous_context:
            tool_args.update(previous_context.get("tool_args") or {})
        tool_args.update(normalize_args(detected_tool, message, tool_args))
        tool_result = executor.execute(user, detected_tool, tool_args)
        append_turn(
            db,
            conversation,
            user_message=message,
            assistant_reply=tool_result.message,
            mode="academic_tools",
            intent=detected_tool,
            tool_code=detected_tool,
            tool_args=tool_args,
            tool_status=tool_result.status,
        )
        return _chat_response(
            session_id=session_id,
            reply=tool_result.message,
            mode="academic_tools",
            intent=detected_tool,
            tool_calls=[tool_result.to_dict()],
            suggested_mode="academic_tools",
        )

    if mode != "auto":
        tool_hint = ""
        if mode == "academic_tools":
            tool_hint = "\n\n当前账号可用系统工具：\n" + "\n".join(
                f"- {tool['code']}：{tool['name']}，权限码 {tool['permission']}，风险 {tool['risk']}"
                for tool in available_tools
            )
        message = f"{MODE_HINTS.get(mode, '')}{tool_hint}\n\n用户问题：{message}"

    try:
        result = ai_service.chat(user, message, db)
    except TypeError:
        result = {
            "reply": "校园助手入口已经就绪。这个问题触发了旧智能助手的数据格式兼容问题，后续接入正式 Agent 工具后会统一返回结构。你可以先继续体验足球入口、能力切换和聊天面板。",
            "intent": "chat_fallback",
        }
    reply = result.get("reply", "")

    intent = result.get("intent", "chat")
    append_turn(
        db,
        conversation,
        user_message=body.message.strip(),
        assistant_reply=reply,
        mode=mode,
        intent=intent,
    )
    return _chat_response(
        session_id=session_id,
        reply=reply,
        mode=mode,
        intent=intent,
        tool_calls=result.get("tool_calls", []),
    )
