"""
人脸识别相关 Schema
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class FaceLoginRequest(BaseModel):
    """人脸登录请求"""
    feature_vector: List[float] = Field(..., description="128维人脸特征向量")
    device_info: Optional[str] = Field(None, description="设备信息")


class FaceEnrollRequest(BaseModel):
    """人脸录入请求"""
    feature_vector: List[float] = Field(..., description="128维人脸特征向量")
    confidence: float = Field(..., description="录入时的置信度")