"""
Notification service.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import PageParams


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    content: str = "",
    category: str = "system",
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        content=content,
        category=category,
        related_type=related_type,
        related_id=related_id,
        is_read=False,
    )
    db.add(notification)
    return notification


def list_notifications(
    user: User,
    params: PageParams,
    db: Session,
    *,
    is_read: Optional[bool] = None,
    category: Optional[str] = None,
):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if is_read is not None:
        q = q.filter(Notification.is_read == is_read)
    if category:
        q = q.filter(Notification.category == category)
    if params.keyword:
        like = f"%{params.keyword}%"
        q = q.filter(or_(Notification.title.like(like), Notification.content.like(like)))
    return q.order_by(Notification.created_at.desc())


def unread_count(user: User, db: Session) -> int:
    return db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).count()


def mark_read(notification_id: int, user: User, db: Session) -> Notification | None:
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if not notification:
        return None
    notification.is_read = True
    notification.read_at = datetime.now()
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(user: User, db: Session) -> int:
    items = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).all()
    now = datetime.now()
    for item in items:
        item.is_read = True
        item.read_at = now
    db.commit()
    return len(items)
