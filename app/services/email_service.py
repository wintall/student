"""
邮件系统服务
"""
import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.email import EmailMessage, EmailAttachment
from app.core.validators import validate_email
from app.exceptions import BusinessException, NotFoundError
from app.config import settings

logger = logging.getLogger("app")


# ============ 工具函数 ============

def _ensure_upload_dir() -> str:
    """确保附件上传目录存在"""
    target_dir = settings.ATTACHMENT_DIR
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def _save_attachment(file_data: bytes, file_name: str, mime_type: str = None) -> Tuple[str, int]:
    """
    保存附件到磁盘
    :return: (相对路径, 文件大小)
    """
    upload_dir = _ensure_upload_dir()

    # 重命名：uuid + 原始扩展名，避免冲突
    ext = os.path.splitext(file_name)[1] or ""
    new_name = f"{uuid.uuid4().hex}{ext}"

    file_path = os.path.join(upload_dir, new_name)

    with open(file_path, "wb") as f:
        f.write(file_data)

    # 相对路径用于 URL 生成
    rel_path = os.path.join("email_attachments", new_name).replace("\\", "/")
    return rel_path, len(file_data)


def _format_email_for_response(msg: EmailMessage) -> dict:
    """格式化邮件响应（将 datetime 转为字符串）"""
    return {
        "id": msg.id,
        "subject": msg.subject,
        "body": msg.body,
        "sender_id": msg.sender_id,
        "sender_name": msg.sender_name,
        "sender_email": msg.sender_email,
        "recipient_email": msg.recipient_email,
        "recipient_user_id": msg.recipient_user_id,
        "is_external": msg.is_external,
        "status": msg.status,
        "is_read": msg.is_read,
        "sent_at": msg.sent_at.strftime("%Y-%m-%d %H:%M:%S") if msg.sent_at else "",
        "attachments": [
            {
                "id": att.id,
                "file_name": att.file_name,
                "file_size": att.file_size,
                "mime_type": att.mime_type,
            }
            for att in (msg.attachments or [])
        ],
    }


# ============ 发邮件 ============

def send_email(sender: User, recipient_email: str, subject: str, body: str,
               attachments: List[dict] = None, db: Session = None) -> EmailMessage:
    """
    发送内部邮件
    - 内部邮件：收件人邮箱在 user 表中存在 → 直接插入数据库作为收件箱记录
    - 外部邮件：收件人邮箱不存在 → 插入数据库 + 通过 SMTP 真实发送
    :param attachments: 附件列表，每项为 {"file_data": bytes, "file_name": str, "mime_type": str}
    """
    if db is None:
        raise BusinessException("缺少数据库会话")

    # 1. 格式校验
    recipient_email = recipient_email.strip().lower()
    valid, msg = validate_email(recipient_email)
    if not valid:
        raise BusinessException(code=400, message=f"收件人邮箱格式不正确: {msg}")

    if not subject or not subject.strip():
        raise BusinessException(code=400, message="邮件主题不能为空")

    # 2. 判断是否为内部用户
    recipient = db.query(User).filter(
        User.email == recipient_email,
        User.is_deleted == False,
    ).first()

    is_external = recipient is None

    # 3. 创建邮件记录（发送方视角）
    msg = EmailMessage(
        sender_id=sender.id,
        sender_name=sender.real_name or sender.username,
        sender_email=sender.email,
        recipient_email=recipient_email,
        recipient_user_id=recipient.id if recipient else None,
        subject=subject.strip(),
        body=body or "",
        is_external=is_external,
        status="sent",
        is_read=False,
        is_deleted_by_sender=False,
        is_deleted_by_recipient=False,
        sent_at=datetime.now(),
    )
    db.add(msg)
    db.flush()

    # 4. 保存附件
    if attachments:
        for att in attachments:
            file_data = att.get("file_data")
            file_name = att.get("file_name")
            mime_type = att.get("mime_type")

            if not file_data or not file_name:
                continue

            # 大小限制
            if len(file_data) > settings.MAX_UPLOAD_SIZE:
                raise BusinessException(code=400, message=f"附件 {file_name} 超过大小限制")

            file_path, file_size = _save_attachment(file_data, file_name, mime_type)

            db.add(EmailAttachment(
                message_id=msg.id,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
            ))

    db.commit()
    db.refresh(msg)

    # 5. 外部邮件：真实发送
    if is_external:
        try:
            from app.utils.email import send_email as _send_smtp
            att_list = [
                {"path": os.path.join(settings.ABS_UPLOAD_DIR, att.file_path), "filename": att.file_name}
                for att in (msg.attachments or [])
            ]
            ok = _send_smtp(
                recipient_email,
                f"[学生信息管理系统] {subject}",
                body or "",
                html=False,
                attachments=att_list,
            )
            if not ok:
                msg.status = "failed"
                db.commit()
                logger.warning(f"外部邮件发送失败: {recipient_email}")
        except Exception as e:
            msg.status = "failed"
            db.commit()
            logger.error(f"外部邮件发送异常: {e}")

    logger.info(f"邮件发送成功: from={sender.email} to={recipient_email} (external={is_external})")
    return msg


# ============ 查询 ============

def get_inbox(user: User, db: Session, page: int = 1, page_size: int = 20, keyword: str = None) -> dict:
    """
    收件箱
    - 内部邮件：recipient_user_id = 当前用户
    - 外部邮件：recipient_email = 当前用户邮箱（防止有人用外部邮箱发）
    """
    query = db.query(EmailMessage).filter(
        EmailMessage.is_deleted_by_recipient == False,
    )

    # 两种情况都接收：内部发给我的 + 邮箱匹配我的
    conditions = []
    if user.id:
        conditions.append(EmailMessage.recipient_user_id == user.id)
    if user.email:
        conditions.append(EmailMessage.recipient_email == user.email.lower())

    if conditions:
        from sqlalchemy import or_
        query = query.filter(or_(*conditions))

    # 关键词过滤
    if keyword:
        like = f"%{keyword}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            EmailMessage.subject.like(like),
            EmailMessage.body.like(like),
            EmailMessage.sender_name.like(like),
        ))

    total = query.count()
    items = query.order_by(EmailMessage.sent_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_email_for_response(m) for m in items],
    }


def get_sent(user: User, db: Session, page: int = 1, page_size: int = 20, keyword: str = None) -> dict:
    """已发送邮件"""
    query = db.query(EmailMessage).filter(
        EmailMessage.sender_id == user.id,
        EmailMessage.is_deleted_by_sender == False,
    )

    if keyword:
        like = f"%{keyword}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            EmailMessage.subject.like(like),
            EmailMessage.body.like(like),
            EmailMessage.recipient_email.like(like),
        ))

    total = query.count()
    items = query.order_by(EmailMessage.sent_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_email_for_response(m) for m in items],
    }


def get_email_detail(email_id: int, user: User, db: Session) -> dict:
    """获取邮件详情（自动标记已读，检查权限）"""
    msg = db.query(EmailMessage).filter(EmailMessage.id == email_id).first()
    if not msg:
        raise NotFoundError("邮件不存在")

    # 权限：必须是发件人或收件人
    is_sender = msg.sender_id == user.id
    is_recipient = msg.recipient_user_id == user.id or (
        user.email and msg.recipient_email == user.email.lower()
    )

    if not is_sender and not is_recipient:
        raise BusinessException(code=403, message="无权查看此邮件")

    # 标记已读（仅收件人视角才标已读）
    if is_recipient and not msg.is_read:
        msg.is_read = True
        db.commit()

    return _format_email_for_response(msg)


# ============ 删除 ============

def delete_email(email_id: int, user: User, db: Session, as_recipient: bool = True):
    """
    删除邮件
    - as_recipient=True：收件人视角删除（标记 is_deleted_by_recipient
    - as_recipient=False：发件人视角删除（标记 is_deleted_by_sender
    - 两个标记都为 True 时可考虑物理删除（此处软删除即可
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == email_id).first()
    if not msg:
        raise NotFoundError("邮件不存在")

    is_sender = msg.sender_id == user.id
    is_recipient = msg.recipient_user_id == user.id or (
        user.email and msg.recipient_email == user.email.lower()
    )

    if not is_sender and not is_recipient:
        raise BusinessException(code=403, message="无权操作此邮件")

    if as_recipient and is_recipient:
        msg.is_deleted_by_recipient = True
    elif not as_recipient and is_sender:
        msg.is_deleted_by_sender = True
    else:
        raise BusinessException(code=403, message="无权从该视角删除此邮件")

    db.commit()


# ============ 搜索用户建议 ============

def search_users(keyword: str, current_user: User, db: Session, limit: int = 10) -> List[dict]:
    """
    搜索用户（用于写信时搜索收件人）
    - 按用户名/真实姓名/邮箱匹配
    - 必须有邮箱字段才能作为结果返回
    """
    keyword = (keyword or "").strip()

    query = db.query(User).filter(
        User.is_deleted == False,
        User.email != None,
        User.email != "",
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (User.username.like(like)) |
            (User.real_name.like(like)) |
            (User.email.like(like))
        )

    users = query.order_by(User.username.asc()).limit(limit + 1).all()

    result = []
    for u in users:
        if u.id == current_user.id:
            continue  # 不推荐自己
        result.append({
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "email": u.email,
        })
        if len(result) >= limit:
            break

    return result


# ============ 未读统计 ============

def get_unread_count(user: User, db: Session) -> int:
    """未读邮件数量"""
    from sqlalchemy import or_
    query = db.query(EmailMessage).filter(
        EmailMessage.is_deleted_by_recipient == False,
        EmailMessage.is_read == False,
    )

    conditions = []
    if user.id:
        conditions.append(EmailMessage.recipient_user_id == user.id)
    if user.email:
        conditions.append(EmailMessage.recipient_email == user.email.lower())

    if conditions:
        query = query.filter(or_(*conditions))

    return query.count()
