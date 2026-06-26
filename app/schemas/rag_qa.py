"""
RAG 问答对 Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class QaPairCreate(BaseModel):
    """创建问答对"""
    category: Optional[str] = Field(default=None, max_length=32, description="分类")
    question: str = Field(..., min_length=1, max_length=255, description="标准问题")
    question_variants: Optional[str] = Field(default=None, max_length=1024, description="问题变体，用分号分隔")
    answer: str = Field(..., min_length=1, description="答案")
    keywords: Optional[str] = Field(default=None, max_length=255, description="关键词，用逗号分隔")
    source: Optional[str] = Field(default=None, max_length=128, description="来源/出处")


class QaPairUpdate(BaseModel):
    """更新问答对"""
    category: Optional[str] = Field(default=None, max_length=32)
    question: Optional[str] = Field(default=None, min_length=1, max_length=255)
    question_variants: Optional[str] = Field(default=None, max_length=1024)
    answer: Optional[str] = Field(default=None, min_length=1)
    keywords: Optional[str] = Field(default=None, max_length=255)
    source: Optional[str] = Field(default=None, max_length=128)
    status: Optional[int] = Field(default=None, description="1=正常, 0=禁用")


class QaPairSearch(BaseModel):
    """搜索问答对参数"""
    keyword: Optional[str] = None
    category: Optional[str] = None
    status: Optional[int] = None
