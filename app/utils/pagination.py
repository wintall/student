"""
通用分页工具
"""
from typing import List, TypeVar, Generic
from sqlalchemy.orm import Query
from app.schemas.common import PageResult, PageParams

T = TypeVar("T")


def paginate(query: Query, params: PageParams, schema_class=None) -> dict:
    """
    通用分页查询
    :param query: SQLAlchemy Query 对象
    :param params: 分页参数
    :param schema_class: Pydantic Schema 类（用于序列化）
    :return: PageResult dict
    """
    total = query.count()
    items = query.offset(params.offset).limit(params.page_size).all()

    if schema_class:
        items = [schema_class.model_validate(item) for item in items]

    return {
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "items": items,
    }
