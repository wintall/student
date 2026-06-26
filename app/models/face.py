"""
人脸识别相关模型
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin


class FaceTemplate(TimestampMixin, Base):
    """人脸模板表 - 存储用户的人脸特征向量"""
    __tablename__ = "face_template"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="关联用户ID")
    feature_vector = Column(Text, nullable=False, comment="人脸特征向量（JSON序列化）")
    confidence = Column(Float, default=0.0, comment="录入时的置信度")
    status = Column(Integer, default=1, comment="1=启用 0=禁用")

    __table_args__ = (UniqueConstraint("user_id", name="uq_face_user"),)

    user = relationship("User", back_populates="face_template")


class FaceLoginLog(Base):
    """人脸登录日志表 - 安全审计"""
    __tablename__ = "face_login_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, comment="匹配到的用户ID")
    confidence = Column(Float, nullable=False, comment="匹配置信度")
    success = Column(Boolean, nullable=False, comment="是否成功")
    message = Column(String(255), nullable=True, comment="结果描述")
    ip_address = Column(String(50), nullable=True, comment="请求IP")
    device_info = Column(String(255), nullable=True, comment="设备信息")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="登录时间")

    user = relationship("User", backref="face_login_logs")