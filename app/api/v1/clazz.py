"""
班级路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import clazz_service
from app.schemas.clazz import ClazzCreate, ClazzUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, clazz_to_dict

router = APIRouter(prefix="/clazzes", tags=["班级管理"])


@router.post("")
def create(body: ClazzCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    clazz = clazz_service.create_clazz(body, db)
    return success(data={"id": clazz.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    department_id: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = clazz_service.list_clazzes(params, db, department_id)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), clazz_to_dict)
    return page_success(result)


@router.get("/{clazz_id}")
def get(clazz_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    clazz = clazz_service.get_clazz(clazz_id, db)
    return success(data=clazz_to_dict(clazz))


@router.put("/{clazz_id}")
def update(clazz_id: int, body: ClazzUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    clazz = clazz_service.update_clazz(clazz_id, body, db)
    return success(data={"id": clazz.id})


@router.delete("/{clazz_id}")
def delete(clazz_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    clazz_service.delete_clazz(clazz_id, db)
    return success(message="删除成功")
