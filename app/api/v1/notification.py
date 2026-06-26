"""
Notification APIs.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import PageParams
from app.services import notification_service
from app.utils.pagination import paginate
from app.utils.response import page_success, success

router = APIRouter(prefix="/notifications", tags=["通知中心"])


def _to_dict(item):
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "category": item.category,
        "related_type": item.related_type,
        "related_id": item.related_id,
        "is_read": item.is_read,
        "read_at": item.read_at.strftime("%Y-%m-%d %H:%M:%S") if item.read_at else "",
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
    }


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    is_read: bool = Query(None),
    category: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = notification_service.list_notifications(user, params, db, is_read=is_read, category=category)
    result = paginate(q, params)
    result["items"] = [_to_dict(item) for item in result.get("items", [])]
    return page_success(result)


@router.get("/unread-count")
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(data={"unread": notification_service.unread_count(user, db)})


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = notification_service.mark_read(notification_id, user, db)
    return success(data=_to_dict(item) if item else None)


@router.post("/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = notification_service.mark_all_read(user, db)
    return success(data={"updated": count})
