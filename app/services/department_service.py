"""
院系服务
"""
from sqlalchemy.orm import Session
from app.models.department import Department
from app.exceptions import BusinessException, NotFoundError
from app.schemas.department import DepartmentCreate, DepartmentUpdate


def create_department(data: DepartmentCreate, db: Session) -> Department:
    if db.query(Department).filter(Department.code == data.code).first():
        raise BusinessException(message="院系代码已存在")
    dept = Department(**data.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def get_department(dept_id: int, db: Session) -> Department:
    dept = db.query(Department).filter(Department.id == dept_id, Department.is_deleted == False).first()
    if not dept:
        raise NotFoundError("院系不存在")
    return dept


def update_department(dept_id: int, data: DepartmentUpdate, db: Session) -> Department:
    dept = get_department(dept_id, db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(dept, k, v)
    db.commit()
    db.refresh(dept)
    return dept


def delete_department(dept_id: int, db: Session):
    dept = get_department(dept_id, db)
    dept.soft_delete()
    db.commit()


def list_departments(db: Session, keyword: str = None):
    q = db.query(Department).filter(Department.is_deleted == False)
    if keyword:
        q = q.filter(Department.name.contains(keyword) | Department.code.contains(keyword))
    return q.all()
