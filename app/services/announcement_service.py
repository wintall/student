"""
公告服务
"""
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sa_func

from app.models.announcement import Announcement, AnnouncementRead
from app.exceptions import NotFoundError, BusinessException
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.schemas.common import PageParams


def create_announcement(data: AnnouncementCreate, publisher_id: int, db: Session) -> Announcement:
    ann = Announcement(
        **data.model_dump(),
        publisher_id=publisher_id,
        published_at=datetime.now() if data.status == 1 else None,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


def get_announcement(ann_id: int, db: Session) -> Announcement:
    ann = db.query(Announcement).filter(
        Announcement.id == ann_id,
        Announcement.is_deleted == False,
    ).first()
    if not ann:
        raise NotFoundError("公告不存在")
    return ann


def update_announcement(ann_id: int, data: AnnouncementUpdate, user_id: int, db: Session) -> Announcement:
    ann = get_announcement(ann_id, db)
    if ann.publisher_id != user_id:
        raise BusinessException(code=403, message="只能编辑自己发布的公告")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] == 1 and not ann.published_at:
        ann.published_at = datetime.now()

    for k, v in update_data.items():
        setattr(ann, k, v)
    db.commit()
    db.refresh(ann)
    return ann


def delete_announcement(ann_id: int, user_id: int, db: Session):
    ann = get_announcement(ann_id, db)
    if ann.publisher_id != user_id:
        raise BusinessException(code=403, message="只能删除自己发布的公告")
    ann.soft_delete()
    db.commit()


def list_announcements(params: PageParams, db: Session):
    q = db.query(Announcement).filter(Announcement.is_deleted == False).order_by(
        Announcement.is_top.desc(),
        Announcement.published_at.desc(),
    )
    if params.keyword:
        q = q.filter(Announcement.title.contains(params.keyword))
    return q


def mark_read(ann_id: int, user_id: int, db: Session):
    """标记公告已读"""
    existing = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == ann_id,
        AnnouncementRead.user_id == user_id,
    ).first()
    if existing:
        return  # 已读

    record = AnnouncementRead(
        announcement_id=ann_id,
        user_id=user_id,
        read_at=datetime.now(),
    )
    db.add(record)
    db.commit()


def get_read_count(ann_id: int, db: Session) -> int:
    return db.query(sa_func.count(AnnouncementRead.id)).filter(
        AnnouncementRead.announcement_id == ann_id
    ).scalar() or 0
