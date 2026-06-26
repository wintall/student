"""
请假模块服务
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import get_user_role_codes
from app.exceptions import BusinessException, NotFoundError, PermissionDenied
from app.models.clazz import Clazz
from app.models.leave import LeaveRequest
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.common import PageParams
from app.schemas.leave import LeaveRequestCreate, LeaveRequestReview

ACTIVE_STATUSES = {"pending", "approved"}
DEPARTMENT_REVIEW_ROLES = {"department_admin", "staff_dean"}
COUNSELOR_REVIEW_ROLES = {"counselor", "staff_counselor"}


def _query_base(db: Session):
    return db.query(LeaveRequest).options(
        joinedload(LeaveRequest.applicant),
        joinedload(LeaveRequest.reviewer),
        joinedload(LeaveRequest.student),
        joinedload(LeaveRequest.teacher),
        joinedload(LeaveRequest.clazz),
        joinedload(LeaveRequest.department),
    ).filter(LeaveRequest.is_deleted == False)


def _duration_hours(start_time: datetime, end_time: datetime) -> Decimal:
    if end_time <= start_time:
        raise BusinessException(message="结束时间必须晚于开始时间")
    hours = Decimal(str((end_time - start_time).total_seconds() / 3600)).quantize(Decimal("0.01"))
    if hours <= 0:
        raise BusinessException(message="请假时长必须大于 0")
    return hours


def _resolve_applicant(user: User, data: LeaveRequestCreate, db: Session) -> dict:
    student = db.query(Student).options(joinedload(Student.clazz).joinedload(Clazz.department)).filter(
        Student.user_id == user.id,
        Student.is_deleted == False,
    ).first()
    teacher = db.query(Teacher).filter(
        Teacher.user_id == user.id,
        Teacher.is_deleted == False,
    ).first()

    applicant_type = data.applicant_type
    if not applicant_type:
        if student and teacher:
            raise BusinessException(message="账号同时关联学生和教职工，请选择请假身份")
        applicant_type = "student" if student else "teacher" if teacher else None

    if applicant_type == "student":
        if not student:
            raise BusinessException(message="当前账号未关联学生信息，不能提交学生请假")
        clazz = student.clazz
        return {
            "applicant_type": "student",
            "student_id": student.id,
            "teacher_id": None,
            "clazz_id": student.clazz_id,
            "department_id": clazz.department_id if clazz else None,
        }

    if applicant_type == "teacher":
        if not teacher:
            raise BusinessException(message="当前账号未关联教职工信息，不能提交教职工请假")
        return {
            "applicant_type": "teacher",
            "student_id": None,
            "teacher_id": teacher.id,
            "clazz_id": None,
            "department_id": teacher.department_id,
        }

    raise BusinessException(message="无法识别请假身份")


def _ensure_no_overlap(user_id: int, start_time: datetime, end_time: datetime, db: Session):
    overlap = db.query(LeaveRequest).filter(
        LeaveRequest.applicant_user_id == user_id,
        LeaveRequest.is_deleted == False,
        LeaveRequest.status.in_(ACTIVE_STATUSES),
        LeaveRequest.start_time < end_time,
        LeaveRequest.end_time > start_time,
    ).first()
    if overlap:
        raise BusinessException(message="该时间段已有待审批或已通过的请假申请")


def create_leave_request(user: User, data: LeaveRequestCreate, db: Session) -> LeaveRequest:
    duration = _duration_hours(data.start_time, data.end_time)
    _ensure_no_overlap(user.id, data.start_time, data.end_time, db)
    applicant = _resolve_applicant(user, data, db)

    req = LeaveRequest(
        applicant_user_id=user.id,
        duration_hours=duration,
        status="pending",
        leave_type=data.leave_type,
        start_time=data.start_time,
        end_time=data.end_time,
        reason=data.reason,
        destination=data.destination,
        contact_phone=data.contact_phone,
        emergency_contact=data.emergency_contact,
        attachment_url=data.attachment_url,
        remark=data.remark,
        **applicant,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return get_leave_request_for_user(req.id, user, db)


def _apply_filters(q, *, status: Optional[str] = None, applicant_type: Optional[str] = None,
                   leave_type: Optional[str] = None, keyword: Optional[str] = None):
    if status:
        q = q.filter(LeaveRequest.status == status)
    if applicant_type:
        q = q.filter(LeaveRequest.applicant_type == applicant_type)
    if leave_type:
        q = q.filter(LeaveRequest.leave_type == leave_type)
    if keyword:
        q = q.join(User, User.id == LeaveRequest.applicant_user_id).filter(
            or_(
                User.real_name.contains(keyword),
                User.username.contains(keyword),
                LeaveRequest.reason.contains(keyword),
            )
        )
    return q


def list_my_leave_requests(user: User, params: PageParams, db: Session,
                           status: str = None, applicant_type: str = None, leave_type: str = None):
    q = _query_base(db).filter(LeaveRequest.applicant_user_id == user.id)
    q = _apply_filters(q, status=status, applicant_type=applicant_type, leave_type=leave_type, keyword=params.keyword)
    return q.order_by(LeaveRequest.created_at.desc())


def _review_scope_query(user: User, db: Session):
    role_codes = get_user_role_codes(user, db)
    q = _query_base(db)

    if "admin" in role_codes:
        return q, "admin"

    conditions = []
    reviewer_role = None

    teacher = db.query(Teacher).filter(Teacher.user_id == user.id, Teacher.is_deleted == False).first()
    if role_codes & DEPARTMENT_REVIEW_ROLES:
        if teacher and teacher.department_id:
            conditions.append(LeaveRequest.department_id == teacher.department_id)
            reviewer_role = "department_admin"

    if role_codes & COUNSELOR_REVIEW_ROLES:
        if teacher:
            clazz_ids = [
                row[0] for row in db.query(Clazz.id).filter(
                    Clazz.counselor_id == teacher.id,
                    Clazz.is_deleted == False,
                ).all()
            ]
            if clazz_ids:
                conditions.append(and_(
                    LeaveRequest.applicant_type == "student",
                    LeaveRequest.clazz_id.in_(clazz_ids),
                ))
                reviewer_role = reviewer_role or "counselor"

    if not conditions:
        raise PermissionDenied("无可审批的请假范围")

    return q.filter(or_(*conditions)), reviewer_role or "reviewer"


def list_review_leave_requests(user: User, params: PageParams, db: Session,
                               status: str = None, applicant_type: str = None, leave_type: str = None):
    q, _ = _review_scope_query(user, db)
    q = q.filter(LeaveRequest.applicant_user_id != user.id)
    q = _apply_filters(q, status=status, applicant_type=applicant_type, leave_type=leave_type, keyword=params.keyword)
    return q.order_by(LeaveRequest.created_at.desc())


def get_leave_request(leave_id: int, db: Session) -> LeaveRequest:
    req = _query_base(db).filter(LeaveRequest.id == leave_id).first()
    if not req:
        raise NotFoundError("请假申请不存在")
    return req


def get_leave_request_for_user(leave_id: int, user: User, db: Session) -> LeaveRequest:
    req = get_leave_request(leave_id, db)
    if req.applicant_user_id == user.id:
        return req

    q, _ = _review_scope_query(user, db)
    visible = q.filter(
        LeaveRequest.id == leave_id,
        LeaveRequest.applicant_user_id != user.id,
    ).first()
    if not visible:
        raise PermissionDenied("无权查看该请假申请")
    return visible


def cancel_leave_request(leave_id: int, user: User, db: Session) -> LeaveRequest:
    req = get_leave_request(leave_id, db)
    if req.applicant_user_id != user.id:
        raise PermissionDenied("只能撤销自己的请假申请")
    if req.status != "pending":
        raise BusinessException(message="只有待审批申请可以撤销")
    req.status = "cancelled"
    db.commit()
    db.refresh(req)
    return req


def _review_leave_request(leave_id: int, user: User, data: LeaveRequestReview, db: Session, status: str) -> LeaveRequest:
    req = get_leave_request(leave_id, db)
    if req.applicant_user_id == user.id:
        raise PermissionDenied("不能审批自己的请假申请")
    if req.status != "pending":
        raise BusinessException(message="只有待审批申请可以审核")

    q, reviewer_role = _review_scope_query(user, db)
    allowed = q.filter(LeaveRequest.id == leave_id).first()
    if not allowed:
        raise PermissionDenied("无权审批该请假申请")

    if status == "rejected" and not (data.review_comment or "").strip():
        raise BusinessException(message="驳回时请填写审批意见")

    req.status = status
    req.reviewer_id = user.id
    req.reviewer_role = reviewer_role
    req.review_comment = data.review_comment
    req.reviewed_at = datetime.now()
    db.commit()
    db.refresh(req)
    return get_leave_request(req.id, db)


def approve_leave_request(leave_id: int, user: User, data: LeaveRequestReview, db: Session) -> LeaveRequest:
    req = _review_leave_request(leave_id, user, data, db, "approved")
    from app.services import attendance_service
    attendance_service.sync_leave_to_attendance(req, user, db)
    db.commit()
    return get_leave_request(req.id, db)


def reject_leave_request(leave_id: int, user: User, data: LeaveRequestReview, db: Session) -> LeaveRequest:
    return _review_leave_request(leave_id, user, data, db, "rejected")
