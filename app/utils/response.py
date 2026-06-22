"""
统一响应封装
"""
from typing import Any, Optional
from app.schemas.common import ApiResponse


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return ApiResponse(code=200, message=message, data=data).model_dump()


def error(code: int = 400, message: str = "操作失败", data: Any = None) -> dict:
    """错误响应"""
    return ApiResponse(code=code, message=message, data=data).model_dump()


def page_success(page_data: dict) -> dict:
    """分页成功响应"""
    return ApiResponse(code=200, message="success", data=page_data).model_dump()
