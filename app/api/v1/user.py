"""
用户管理路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.services import user_service
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, user_to_dict

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.post("")
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("system:user:create"))):
    user = user_service.create_user(body, db)
    return success(data={"id": user.id})


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("system:user:list")),
):
    from app.models.user import User as UserModel
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = db.query(UserModel).filter(UserModel.is_deleted == False)
    if keyword:
        q = q.filter(
            UserModel.username.contains(keyword) |
            UserModel.real_name.contains(keyword) |
            UserModel.phone.contains(keyword)
        )
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), user_to_dict)
    return page_success(result)


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("system:user:list"))):
    user = user_service.get_user(user_id, db)
    return success(data=user_to_dict(user))


@router.put("/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("system:user:update"))):
    user = user_service.update_user(user_id, body, db)
    return success(data={"id": user.id})


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("system:user:delete"))):
    user_service.delete_user(user_id, db)
    return success(message="删除成功")
