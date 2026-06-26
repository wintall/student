"""
成绩路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import get_user_role_codes
from app.deps import get_db, require_permission
from app.exceptions import PermissionDenied
from app.models.student import Student
from app.models.user import User
from app.services import score_service
from app.schemas.score import ScoreCreate, ScoreUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, score_to_dict

router = APIRouter(prefix="/scores", tags=["成绩管理"])


@router.post("")
def create(body: ScoreCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:score:create"))):
    s = score_service.create_score(body, db)
    return success(data={"id": s.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exam_id: int = Query(None),
    student_id: int = Query(None),
    course_id: int = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("teaching:score:list")),
):
    params = PageParams(page=page, page_size=page_size)
    role_codes = get_user_role_codes(user, db)
    if role_codes == {"student"}:
        current_student = db.query(Student).filter(
            Student.user_id == user.id,
            Student.is_deleted == False,
        ).first()
        if not current_student:
            raise PermissionDenied("当前账号未关联学生信息")
        student_id = current_student.id
    q = score_service.list_scores(params, db, exam_id, student_id, course_id)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), score_to_dict)
    return page_success(result)


@router.put("/{score_id}")
def update(score_id: int, body: ScoreUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:score:update"))):
    s = score_service.update_score(score_id, body, db)
    return success(data={"id": s.id})


@router.delete("/{score_id}")
def delete(score_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:score:delete"))):
    score_service.delete_score(score_id, db)
    return success(message="删除成功")
