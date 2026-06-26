"""
教职工服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.teacher import Teacher
from app.exceptions import BusinessException, NotFoundError
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.schemas.common import PageParams
from app.services.account_helper import ensure_person_user, update_user_contact


POSITION_LABELS = {
    0: "教师",
    1: "系主任",
    2: "院长",
    3: "副校长",
}


def _normalize_position(value):
    return POSITION_LABELS.get(value, value)


def create_teacher(data: TeacherCreate, db: Session) -> Teacher:
    data_dict = data.model_dump()
    phone = data_dict.pop("phone", None)
    email = data_dict.pop("email", None)
    data_dict["position"] = _normalize_position(data_dict.get("position"))
    user = ensure_person_user(
        db,
        user_id=data_dict.get("user_id"),
        username=data.employee_no,
        real_name=data.name,
        phone=phone,
        email=email,
        id_card=data.id_card,
        role_code="teacher",
    )
    data_dict["user_id"] = user.id

    if db.query(Teacher).filter(Teacher.user_id == user.id).first():
        raise BusinessException(message="该用户已关联教职工")
    if db.query(Teacher).filter(Teacher.employee_no == data.employee_no).first():
        raise BusinessException(message="工号已存在")
    if db.query(Teacher).filter(Teacher.id_card == data.id_card).first():
        raise BusinessException(message="身份证号已注册")

    teacher = Teacher(**data_dict)
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
    update_data = data.model_dump(exclude_unset=True)
    phone = update_data.pop("phone", None)
    email = update_data.pop("email", None)
    if "position" in update_data:
        update_data["position"] = _normalize_position(update_data["position"])
    if data.employee_no and data.employee_no != teacher.employee_no:
        if db.query(Teacher).filter(Teacher.employee_no == data.employee_no, Teacher.id != teacher_id).first():
            raise BusinessException(message="工号已存在")
    if data.id_card and data.id_card != teacher.id_card:
        if db.query(Teacher).filter(Teacher.id_card == data.id_card, Teacher.id != teacher_id).first():
            raise BusinessException(message="身份证号已注册")

    for k, v in update_data.items():
        setattr(teacher, k, v)
    if teacher.user:
        update_user_contact(
            teacher.user,
            db,
            real_name=update_data.get("name"),
            phone=phone,
            email=email,
            id_card=update_data.get("id_card"),
        )
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
