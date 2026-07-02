"""Emotion companion module with human-in-the-loop escalation."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clazz import Clazz
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import Role, User, UserRole
from app.services.campus_agent.llm_client import call_deepseek
from app.services.campus_agent.pending_actions import create_pending_action
from app.services import email_service


HIGH_RISK_KEYWORDS = [
    "自杀",
    "轻生",
    "想死",
    "不想活",
    "活不下去",
    "结束生命",
    "伤害自己",
    "自残",
    "割腕",
    "跳楼",
]

MEDIUM_RISK_KEYWORDS = [
    "崩溃",
    "绝望",
    "撑不住",
    "抑郁",
    "焦虑",
    "痛苦",
    "失眠",
    "厌学",
    "压力大",
    "心情不好",
    "没有意义",
    "很累",
]


def risk_level(message: str) -> str:
    text = message or ""
    if any(word in text for word in HIGH_RISK_KEYWORDS):
        return "high"
    if any(word in text for word in MEDIUM_RISK_KEYWORDS):
        return "medium"
    return "low"


def _student_profile(user: User, db: Session) -> Student | None:
    return db.query(Student).filter(Student.user_id == user.id, Student.is_deleted == False).first()


def _care_recipients(student: Student | None, db: Session) -> list[User]:
    if not student:
        return []
    recipients: list[User] = []

    def add_teacher(teacher: Teacher | None) -> None:
        if teacher and teacher.user and teacher.user.email and teacher.user not in recipients:
            recipients.append(teacher.user)

    clazz = db.query(Clazz).filter(Clazz.id == student.clazz_id).first()
    if clazz and clazz.counselor_id:
        teacher = db.query(Teacher).filter(Teacher.id == clazz.counselor_id, Teacher.is_deleted == False).first()
        add_teacher(teacher)

    if clazz and clazz.department_id:
        teachers = (
            db.query(Teacher)
            .filter(Teacher.department_id == clazz.department_id, Teacher.is_deleted == False, Teacher.status == 1)
            .all()
        )
        priority_words = ("主任", "院长", "书记", "辅导员", "学生工作", "学工")
        priority = [
            teacher
            for teacher in teachers
            if any(word in f"{teacher.position or ''}{teacher.title or ''}" for word in priority_words)
        ]
        for teacher in priority:
            add_teacher(teacher)
            if len(recipients) >= 3:
                return recipients
        for teacher in teachers:
            add_teacher(teacher)
            if len(recipients) >= 3:
                break
    return recipients


def _admin_recipients(db: Session) -> list[User]:
    admins = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            Role.code == "admin",
            User.is_deleted == False,
            User.status == 1,
            User.email != None,
            User.email != "",
        )
        .all()
    )
    if admins:
        return admins
    fallback = (
        db.query(User)
        .filter(
            User.username == "admin",
            User.is_deleted == False,
            User.status == 1,
            User.email != None,
            User.email != "",
        )
        .all()
    )
    return fallback


def _merge_recipients(*groups: list[User]) -> list[User]:
    result: list[User] = []
    seen: set[str] = set()
    for group in groups:
        for user in group:
            email = (user.email or "").strip().lower()
            if not email or email in seen:
                continue
            seen.add(email)
            result.append(user)
    return result


def _safe_student_label(student: Student | None, user: User) -> str:
    if student:
        return f"{student.name}（学号：{student.student_no}）"
    return f"{user.real_name or user.username}（用户ID：{user.id}）"


def _emotion_email_subject(level: str, student: Student | None, user: User) -> str:
    prefix = "高风险情绪安全提醒" if level == "high" else "学生情绪状态关注提醒"
    return f"{prefix}：{student.name if student else user.real_name or user.username}"


def _emotion_email_body(level: str, student: Student | None, user: User, message: str) -> str:
    label = _safe_student_label(student, user)
    if level == "high":
        return (
            f"系统检测到 {label} 在校园助手中表达了可能涉及生命安全或自我伤害的高风险内容。\n"
            "请相关责任人尽快以关怀、非责备的方式进行线下联系，优先确认其当前位置、安全状态和身边是否有人陪伴。\n\n"
            "隐私说明：为减少不必要扩散，系统仅提示存在高风险情绪信号，不在邮件中转发完整对话原文。\n"
            f"必要摘要：{message[:120]}\n\n"
            "处理建议：\n"
            "1. 优先联系学生本人，语气保持稳定和支持。\n"
            "2. 如无法联系本人，请联系班主任/辅导员、院系负责人或紧急联系人协助确认安全。\n"
            "3. 如判断存在立即危险，请按学校危机干预流程或当地紧急服务处理。\n\n"
            "说明：此提醒不代表医学诊断，仅用于人在回路的安全关怀跟进。"
        )
    return (
        f"系统检测到 {label} 在校园助手中表达了较明显的负面情绪或压力状态。\n"
        "请班主任/院系老师尽快以关怀方式联系学生，确认其支持需求。\n\n"
        f"学生原话摘要：{message[:300]}\n\n"
        "说明：此提醒不代表医学诊断，仅用于人在回路的关怀跟进。"
    )


def _send_emotion_alerts(sender: User, recipients: list[User], subject: str, body: str, db: Session) -> list[dict]:
    sent = []
    for recipient in recipients:
        msg = email_service.send_email(
            sender=sender,
            recipient_email=recipient.email,
            subject=subject,
            body=body,
            attachments=None,
            db=db,
        )
        sent.append({
            "id": msg.id,
            "email": recipient.email,
            "name": recipient.real_name or recipient.username,
        })
    return sent


def _professional_fallback(message: str, context_messages: list[str] | None = None) -> str:
    context = "、".join([item.strip() for item in (context_messages or []) if item.strip()])
    situation = context or message.strip() or "最近情绪和压力状态不太好"
    return (
        f"我先按你前面提到的情况来理解：{situation}。这类状态通常不是“意志力差”，更常见的是压力源持续存在时，"
        "大脑进入高警觉和消耗模式，注意力、睡眠、效率都会被影响；效率下降又容易带来自责，形成“压力-回避-自责-更焦虑”的循环。\n\n"
        "可以先用一个 CBT 的小练习把循环拆开：写下“触发事件-自动想法-情绪强度-行为反应”。例如“任务很多 -> 我肯定完不成 -> 焦虑 80 分 -> 刷手机逃避”。"
        "然后问自己三个问题：证据是什么？有没有更平衡的说法？下一步最小行动是什么？这个练习的目的不是强行乐观，而是把情绪从一团雾变成可处理的信息。\n\n"
        "接下来建议你做 3 件具体的事：第一，把今天任务缩到一个 15 分钟行动，只求启动，不求完美；第二，做 2 分钟缓慢呼吸或正念落地练习，"
        "把注意力放回身体和当下；第三，找一个可信任的人说清楚“我最近压力很大，需要有人听我讲一会儿”。WHO 的压力管理指南和 ACT 都强调，"
        "压力下先回到当下、再做符合价值的小行动，比反复责备自己更有效。\n\n"
        "如果低落、失眠、食欲明显变化、无望感或无法学习的状态持续两周以上，建议联系学校心理老师做一次正式评估。"
        "如果出现伤害自己、活不下去、已经有计划等想法，请立刻联系身边可信任的人、班主任/辅导员、家人，或拨打当地紧急电话。"
    )


def companion_reply(message: str, context_messages: list[str] | None = None) -> str:
    context_text = "\n".join(item.strip() for item in (context_messages or []) if item.strip())
    system_prompt = (
        "你是校园智能助手中的专业心理支持助手，面向学生和教职工提供支持性心理辅导。"
        "你不是医生，不能做医学诊断，不能声称替代心理咨询或治疗；但回答要体现专业心理学素养。"
        "优先使用成熟框架：认知行为疗法 CBT 的想法-情绪-行为链条、压力与应对模型、行为激活、"
        "ACT 的接纳与价值行动、正念/落地技术、睡眠运动和社会支持等保护因素。"
        "回答要像咨询室里的初步支持：先准确共情和概括用户处境，再解释可能的心理机制，"
        "再给出 2-4 个可执行练习，最后说明什么情况下应联系学校心理老师或专业机构。"
        "可以提到依据来自 WHO 压力管理指南、APA 压力应对建议、CBT/ACT 等常见心理学框架，"
        "但不要编造论文、作者、诊断结论或夸大疗效。"
        "如果出现自伤、自杀、活不下去、明确计划等高风险内容，优先做安全回应："
        "建议用户立刻联系身边可信任的人、班主任/辅导员/家人、学校心理中心或当地紧急服务。"
        "语气要稳定、专业、具体、自然，不要只给喝水、散步这类浅层建议。"
    )
    user_message = (
        f"最近对话背景：\n{context_text}\n\n当前用户输入：{message}"
        if context_text
        else message
    )
    reply = call_deepseek(system_prompt=system_prompt, user_message=user_message, temperature=0.45, max_tokens=1200)
    return reply or _professional_fallback(message, context_messages=context_messages)


def handle_emotion_message(
    user: User,
    db: Session,
    session_id: str,
    message: str,
    context_messages: list[str] | None = None,
) -> tuple[str, dict]:
    combined_text = "\n".join([*(context_messages or []), message])
    level = risk_level(combined_text)
    reply = companion_reply(message, context_messages=context_messages)
    data = {"risk_level": level}
    if level == "low":
        return reply, data

    student = _student_profile(user, db)
    care_recipients = _care_recipients(student, db)
    admin_recipients = _admin_recipients(db)
    recipients = _merge_recipients(care_recipients, admin_recipients)
    if not student or not recipients:
        extra = (
            "\n\n我建议你现在联系身边可信任的人、班主任/辅导员或家人。"
            "如果你有立刻伤害自己的冲动，请马上拨打当地紧急电话，或去最近的安全地点寻求当面帮助。"
        )
        data["escalation"] = "no_student_or_recipient"
        return reply + extra, data

    subject = _emotion_email_subject(level, student, user)
    body = _emotion_email_body(level, student, user, message)
    if level == "high":
        try:
            sent = _send_emotion_alerts(user, recipients, subject, body, db)
            data.update({
                "escalation": "auto_sent",
                "recipients": [{"name": item.real_name or item.username, "email": item.email} for item in recipients],
                "sent": sent,
            })
            extra = (
                "\n\n我已经帮你向校内安全联系人发送了高风险关怀提醒，包括班主任/院系老师和系统管理员。"
                "邮件只包含最小必要信息，用于尽快确认你的安全，不会公开完整对话。"
                "现在请你优先做一件事：联系身边可信任的人，或去有人在的安全地点。"
            )
            return reply + extra, data
        except Exception as exc:
            data.update({"escalation": "auto_send_failed", "error": str(exc)})
            extra = (
                "\n\n我尝试发送高风险关怀提醒，但发送失败。"
                "请你现在立刻联系身边可信任的人、班主任/辅导员或家人；如果有立即伤害自己的冲动，请拨打当地紧急电话。"
            )
            return reply + extra, data

    summary = (
        "检测到你可能处在比较痛苦或需要支持的状态。\n"
        "我可以帮你通知班主任/院系老师和系统管理员做关怀跟进，确认后才会发送：\n"
        + "\n".join(f"- {item.real_name or item.username} <{item.email}>" for item in recipients)
    )
    pending = create_pending_action(
        db,
        user=user,
        session_id=session_id,
        tool_code="emotion_care_email",
        args={
            "recipient_emails": [item.email for item in recipients],
            "subject": subject,
            "body": body,
        },
        summary=summary,
        risk="high" if level == "high" else "medium",
    )
    data.update(
        {
            "pending_action_id": pending.id,
            "recipients": [{"name": item.real_name or item.username, "email": item.email} for item in recipients],
        }
    )
    extra = (
        f"\n\n我也可以通知你的班主任/院系老师和系统管理员帮你做关怀跟进。"
        f"待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后发送，10 分钟内有效。"
        "\n如果你现在有伤害自己的冲动，请立刻联系身边的人或拨打当地紧急电话。"
    )
    return reply + extra, data
