"""
班级服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.clazz import Clazz
from app.models.department import Department
from app.models.teacher import Teacher
from app.exceptions import BusinessException, NotFoundError
from app.schemas.clazz import ClazzCreate, ClazzUpdate
from app.schemas.common import PageParams


def create_clazz(data: ClazzCreate, db: Session) -> Clazz:
    if db.query(Clazz).filter(Clazz.code == data.code).first():
        raise BusinessException(message="班级代码已存在")
    if not db.query(Department).filter(Department.id == data.department_id, Department.is_deleted == False).first():
        raise NotFoundError("院系不存在")
    clazz = Clazz(**data.model_dump())
    db.add(clazz)
    db.commit()
    db.refresh(clazz)
    return clazz


def get_clazz(clazz_id: int, db: Session) -> Clazz:
    clazz = db.query(Clazz).options(
        joinedload(Clazz.department),
        joinedload(Clazz.counselor),
    ).filter(Clazz.id == clazz_id, Clazz.is_deleted == False).first()
    if not clazz:
        raise NotFoundError("班级不存在")
    return clazz


def update_clazz(clazz_id: int, data: ClazzUpdate, db: Session) -> Clazz:
    clazz = get_clazz(clazz_id, db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(clazz, k, v)
    db.commit()
    db.refresh(clazz)
    return clazz


def delete_clazz(clazz_id: int, db: Session):
    clazz = get_clazz(clazz_id, db)
    clazz.soft_delete()
    db.commit()


def list_clazzes(params: PageParams, db: Session, department_id: int = None):
    q = db.query(Clazz).options(
        joinedload(Clazz.department),
        joinedload(Clazz.counselor),
    ).filter(Clazz.is_deleted == False)
    if department_id:
        q = q.filter(Clazz.department_id == department_id)
    if params.keyword:
        q = q.filter(Clazz.name.contains(params.keyword) | Clazz.code.contains(params.keyword))
    return q
