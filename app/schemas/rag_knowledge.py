from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    scope_type: str = Field(default="personal", pattern="^(personal|public|class|course)$")
    scope_id: Optional[int] = None
    chunk_strategy: str = Field(default="paragraph", pattern="^(paragraph|fixed)$")
    chunk_size: int = Field(default=700, ge=200, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)
    embedding_model: str = Field(default="moka-ai/m3e-base", max_length=100)
    vector_store: str = Field(default="milvus", pattern="^(milvus)$")
    similarity_metric: str = Field(default="COSINE", pattern="^(COSINE|IP|L2)$")
    retrieval_mode: str = Field(default="hybrid", pattern="^(vector|keyword|hybrid)$")
    default_top_k: int = Field(default=5, ge=1, le=20)
    default_min_score: int = Field(default=45, ge=0, le=100)
    vector_weight: int = Field(default=62, ge=0, le=100)
    bm25_weight: int = Field(default=28, ge=0, le=100)
    title_weight: int = Field(default=10, ge=0, le=100)
    core_weight: int = Field(default=35, ge=0, le=100)


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    scope_type: Optional[str] = Field(default=None, pattern="^(personal|public|class|course)$")
    scope_id: Optional[int] = None
    status: Optional[int] = Field(default=None, ge=0, le=1)
    chunk_strategy: Optional[str] = Field(default=None, pattern="^(paragraph|fixed)$")
    chunk_size: Optional[int] = Field(default=None, ge=200, le=2000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=500)
    embedding_model: Optional[str] = Field(default=None, max_length=100)
    vector_store: Optional[str] = Field(default=None, pattern="^(milvus)$")
    similarity_metric: Optional[str] = Field(default=None, pattern="^(COSINE|IP|L2)$")
    retrieval_mode: Optional[str] = Field(default=None, pattern="^(vector|keyword|hybrid)$")
    default_top_k: Optional[int] = Field(default=None, ge=1, le=20)
    default_min_score: Optional[int] = Field(default=None, ge=0, le=100)
    vector_weight: Optional[int] = Field(default=None, ge=0, le=100)
    bm25_weight: Optional[int] = Field(default=None, ge=0, le=100)
    title_weight: Optional[int] = Field(default=None, ge=0, le=100)
    core_weight: Optional[int] = Field(default=None, ge=0, le=100)


class TextImportRequest(BaseModel):
    kb_id: int
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1)


class PathImportRequest(BaseModel):
    kb_id: int
    path: str = Field(..., min_length=1, max_length=500)
    title: Optional[str] = Field(default=None, max_length=200)


class KnowledgeSearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    kb_ids: Optional[List[int]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class KnowledgeAskRequest(KnowledgeSearchRequest):
    session_id: Optional[str] = Field(default=None, max_length=64)


class KnowledgeBaseOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    scope_type: str
    scope_id: Optional[int] = None
    status: int
    document_count: int
    chunk_count: int
    created_at: str
    updated_at: str


class DocumentOut(BaseModel):
    id: int
    kb_id: int
    title: str
    source_type: str
    file_name: Optional[str] = None
    file_ext: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    chunk_count: int
    char_count: int
    created_at: str
    updated_at: str
