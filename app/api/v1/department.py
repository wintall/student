"""
院系路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.services import department_service
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.utils.response import success
from app.utils.entity_mappers import map_entities, department_to_dict

router = APIRouter(prefix="/departments", tags=["院系管理"])


@router.post("")
def create(body: DepartmentCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("org:department:create"))):
    dept = department_service.create_department(body, db)
    return success(data={"id": dept.id})


@router.get("")
def list_all(keyword: str = Query(None), db: Session = Depends(get_db), _: User = Depends(require_permission("org:department:list"))):
    depts = department_service.list_departments(db, keyword)
    return success(data=map_entities(depts, department_to_dict))


@router.get("/{dept_id}")
def get(dept_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("org:department:list"))):
    dept = department_service.get_department(dept_id, db)
    return success(data=department_to_dict(dept))


@router.put("/{dept_id}")
def update(dept_id: int, body: DepartmentUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("org:department:update"))):
    dept = department_service.update_department(dept_id, body, db)
    return success(data={"id": dept.id})


@router.delete("/{dept_id}")
def delete(dept_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("org:department:delete"))):
    department_service.delete_department(dept_id, db)
    return success(message="删除成功")
