"""
学生服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.student import Student
from app.models.clazz import Clazz
from app.exceptions import BusinessException, NotFoundError
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.common import PageParams
from app.services.account_helper import ensure_person_user, update_user_contact


def create_student(data: StudentCreate, db: Session) -> Student:
    data_dict = data.model_dump()
    phone = data_dict.pop("phone", None)
    email = data_dict.pop("email", None)
    user = ensure_person_user(
        db,
        user_id=data_dict.get("user_id"),
        username=data.student_no,
        real_name=data.name,
        phone=phone,
        email=email,
        id_card=data.id_card,
        role_code="student",
    )
    data_dict["user_id"] = user.id

    if db.query(Student).filter(Student.user_id == user.id).first():
        raise BusinessException(message="该用户已关联学生")
    if db.query(Student).filter(Student.student_no == data.student_no).first():
        raise BusinessException(message="学号已存在")
    if db.query(Student).filter(Student.id_card == data.id_card).first():
        raise BusinessException(message="身份证号已注册")

    student = Student(**data_dict)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def get_student(student_id: int, db: Session) -> Student:
    student = db.query(Student).options(
        joinedload(Student.user),
        joinedload(Student.clazz).joinedload(Clazz.department),
    ).filter(Student.id == student_id, Student.is_deleted == False).first()
    if not student:
        raise NotFoundError("学生不存在")
    return student


def update_student(student_id: int, data: StudentUpdate, db: Session) -> Student:
    student = get_student(student_id, db)
    update_data = data.model_dump(exclude_unset=True)
    phone = update_data.pop("phone", None)
    email = update_data.pop("email", None)
    if data.student_no and data.student_no != student.student_no:
        if db.query(Student).filter(Student.student_no == data.student_no, Student.id != student_id).first():
            raise BusinessException(message="学号已存在")
    if data.id_card and data.id_card != student.id_card:
        if db.query(Student).filter(Student.id_card == data.id_card, Student.id != student_id).first():
            raise BusinessException(message="身份证号已注册")

    for k, v in update_data.items():
        setattr(student, k, v)
    if student.user:
        update_user_contact(
            student.user,
            db,
            real_name=update_data.get("name"),
            phone=phone,
            email=email,
            id_card=update_data.get("id_card"),
        )
    db.commit()
    db.refresh(student)
    return student


def delete_student(student_id: int, db: Session):
    student = get_student(student_id, db)
    student.soft_delete()
    db.commit()


def list_students(params: PageParams, db: Session, clazz_id: int = None):
    q = db.query(Student).options(
        joinedload(Student.user),
        joinedload(Student.clazz).joinedload(Clazz.department),
    ).filter(Student.is_deleted == False)
    if clazz_id:
        q = q.filter(Student.clazz_id == clazz_id)
    if params.keyword:
        q = q.filter(
            Student.name.contains(params.keyword) |
            Student.student_no.contains(params.keyword)
        )
    return q
