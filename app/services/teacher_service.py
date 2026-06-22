"""
教职工服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.teacher import Teacher
from app.models.user import User
from app.exceptions import BusinessException, NotFoundError
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.schemas.common import PageParams


def create_teacher(data: TeacherCreate, db: Session) -> Teacher:
    # 检查 user_id 是否存在
    user = db.query(User).filter(User.id == data.user_id, User.is_deleted == False).first()
    if not user:
        raise NotFoundError("关联用户不存在")
    if db.query(Teacher).filter(Teacher.user_id == data.user_id).first():
        raise BusinessException(message="该用户已关联教职工")
    if db.query(Teacher).filter(Teacher.employee_no == data.employee_no).first():
        raise BusinessException(message="工号已存在")
    if db.query(Teacher).filter(Teacher.id_card == data.id_card).first():
        raise BusinessException(message="身份证号已注册")

    teacher = Teacher(**data.model_dump())
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def get_teacher(teacher_id: int, db: Session) -> Teacher:
    teacher = db.query(Teacher).options(
        joinedload(Teacher.user),
        joinedload(Teacher.department),
    ).filter(Teacher.id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        raise NotFoundError("教职工不存在")
    return teacher


def update_teacher(teacher_id: int, data: TeacherUpdate, db: Session) -> Teacher:
    teacher = get_teacher(teacher_id, db)
    if data.employee_no and data.employee_no != teacher.employee_no:
        if db.query(Teacher).filter(Teacher.employee_no == data.employee_no, Teacher.id != teacher_id).first():
            raise BusinessException(message="工号已存在")
    if data.id_card and data.id_card != teacher.id_card:
        if db.query(Teacher).filter(Teacher.id_card == data.id_card, Teacher.id != teacher_id).first():
            raise BusinessException(message="身份证号已注册")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(teacher, k, v)
    db.commit()
    db.refresh(teacher)
    return teacher


def delete_teacher(teacher_id: int, db: Session):
    teacher = get_teacher(teacher_id, db)
    teacher.soft_delete()
    db.commit()


def list_teachers(params: PageParams, db: Session, department_id: int = None):
    q = db.query(Teacher).options(
        joinedload(Teacher.user),
        joinedload(Teacher.department),
    ).filter(Teacher.is_deleted == False)
    if department_id:
        q = q.filter(Teacher.department_id == department_id)
    if params.keyword:
        q = q.filter(
            Teacher.name.contains(params.keyword) |
            Teacher.employee_no.contains(params.keyword)
        )
    return q
