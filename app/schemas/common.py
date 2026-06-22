"""
通用 Schema：ApiResponse 统一响应、PageParams 分页参数
"""
from typing import Any, Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class PageParams(BaseModel):
    """分页请求参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(default=None, description="搜索关键词")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PageResult(BaseModel, Generic[T]):
    """分页响应"""
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[T] = []
