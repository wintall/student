"""
公告路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.services import announcement_service
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, announcement_to_dict

router = APIRouter(prefix="/announcements", tags=["公告管理"])


@router.post("")
def create(body: AnnouncementCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("announcement:publish"))):
    ann = announcement_service.create_announcement(body, user.id, db)
    return success(data={"id": ann.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("announcement:list:view")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = announcement_service.list_announcements(params, db)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), announcement_to_dict)
    return page_success(result)


@router.get("/{ann_id}")
def get(ann_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("announcement:list:view"))):
    ann = announcement_service.get_announcement(ann_id, db)
    return success(data=announcement_to_dict(ann))


@router.put("/{ann_id}")
def update(ann_id: int, body: AnnouncementUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("announcement:update"))):
    ann = announcement_service.update_announcement(ann_id, body, user.id, db)
    return success(data={"id": ann.id})


@router.delete("/{ann_id}")
def delete(ann_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("announcement:delete"))):
    announcement_service.delete_announcement(ann_id, user.id, db)
    return success(message="删除成功")


@router.post("/{ann_id}/read")
def mark_read(ann_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    announcement_service.mark_read(ann_id, user.id, db)
    return success(message="已标记为已读")
