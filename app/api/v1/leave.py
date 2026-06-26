"""
请假模块路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.schemas.common import PageParams
from app.schemas.leave import LeaveRequestCreate, LeaveRequestReview
from app.services import leave_service
from app.utils.entity_mappers import leave_request_to_dict, map_entities
from app.utils.pagination import paginate
from app.utils.response import page_success, success

router = APIRouter(prefix="/leave/requests", tags=["请假管理"])


@router.post("")
def create(
    body: LeaveRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:request:create")),
):
    req = leave_service.create_leave_request(user, body, db)
    return success(data=leave_request_to_dict(req), message="提交成功")


@router.get("/my")
def list_my(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    applicant_type: str = Query(None),
    leave_type: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:request:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = leave_service.list_my_leave_requests(user, params, db, status, applicant_type, leave_type)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), leave_request_to_dict)
    return page_success(result)


@router.get("/review")
def list_review(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    applicant_type: str = Query(None),
    leave_type: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:review:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = leave_service.list_review_leave_requests(user, params, db, status, applicant_type, leave_type)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), leave_request_to_dict)
    return page_success(result)


@router.get("/{leave_id}")
def get(
    leave_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:request:list")),
):
    req = leave_service.get_leave_request_for_user(leave_id, user, db)
    return success(data=leave_request_to_dict(req))


@router.post("/{leave_id}/cancel")
def cancel(
    leave_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:request:cancel")),
):
    req = leave_service.cancel_leave_request(leave_id, user, db)
    return success(data=leave_request_to_dict(req), message="撤销成功")


@router.post("/{leave_id}/approve")
def approve(
    leave_id: int,
    body: LeaveRequestReview,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:review:approve")),
):
    req = leave_service.approve_leave_request(leave_id, user, body, db)
    return success(data=leave_request_to_dict(req), message="审批通过")


@router.post("/{leave_id}/reject")
def reject(
    leave_id: int,
    body: LeaveRequestReview,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("leave:review:reject")),
):
    req = leave_service.reject_leave_request(leave_id, user, body, db)
    return success(data=leave_request_to_dict(req), message="已驳回")
