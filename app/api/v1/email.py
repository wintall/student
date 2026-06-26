"""
邮件系统路由
"""
import os
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.deps import get_db, get_current_user
from app.models.user import User
from app.models.email import EmailMessage, EmailAttachment
from app.services import email_service
from app.config import settings
from app.utils.response import success

router = APIRouter(prefix="/emails", tags=["邮件系统"])


@router.get("/inbox")
def inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """收件箱列表"""
    result = email_service.get_inbox(user, db, page=page, page_size=page_size, keyword=keyword)
    return success(data=result)


@router.get("/sent")
def sent_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """已发送邮件列表"""
    result = email_service.get_sent(user, db, page=page, page_size=page_size, keyword=keyword)
    return success(data=result)


@router.get("/unread-count")
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """未读邮件数量"""
    count = email_service.get_unread_count(user, db)
    return success(data={"unread": count})


@router.get("/{email_id}")
def email_detail(
    email_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """邮件详情（查看时自动标记已读）"""
    data = email_service.get_email_detail(email_id, user, db)
    return success(data=data)


@router.post("/send")
async def send_email(
    recipient_email: str = Form(..., description="收件人邮箱"),
    subject: str = Form(..., description="邮件主题"),
    body: str = Form("", description="邮件正文"),
    files: Optional[List[UploadFile]] = File(None, description="附件"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    发送邮件（支持附件）
    - 内部用户：直接存入数据库收件箱
    - 外部邮箱：数据库记录 + 通过 SMTP 真实发送
    """
    # 处理附件
    attachment_list = []
    if files:
        for f in files:
            try:
                file_data = await f.read()
                attachment_list.append({
                    "file_data": file_data,
                    "file_name": f.filename or "unnamed",
                    "mime_type": f.content_type,
                })
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"附件读取失败: {e}")

    msg = email_service.send_email(
        sender=user,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        attachments=attachment_list,
        db=db,
    )

    return success(
        data={"id": msg.id, "is_external": msg.is_external, "status": msg.status},
        message="邮件发送成功",
    )


@router.delete("/{email_id}")
def delete_email(
    email_id: int,
    as_recipient: bool = Query(True, description="True=收件箱删除, False=已发送删除"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除邮件（软删除）"""
    email_service.delete_email(email_id, user, db, as_recipient=as_recipient)
    return success(message="删除成功")


@router.get("/users/suggest")
def suggest_users(
    keyword: str = Query("", description="搜索关键词"),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """搜索用户建议（写信时搜索收件人用）"""
    users = email_service.search_users(keyword, user, db, limit=limit)
    return success(data=users)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    下载附件
    - 权限：只能下载自己发送或接收到的邮件的附件
    """
    att = db.query(EmailAttachment).filter(EmailAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")

    # 校验用户是否有权访问
    msg = db.query(EmailMessage).filter(EmailMessage.id == att.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="邮件不存在")

    is_sender = msg.sender_id == user.id
    is_recipient = msg.recipient_user_id == user.id or (
        user.email and msg.recipient_email == user.email.lower()
    )

    if not is_sender and not is_recipient:
        raise HTTPException(status_code=403, detail="无权下载此附件")

    # 构造绝对路径
    abs_path = os.path.join(settings.ABS_UPLOAD_DIR, att.file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件已被移除")

    return FileResponse(
        path=abs_path,
        filename=att.file_name,
        media_type=att.mime_type or "application/octet-stream",
    )
