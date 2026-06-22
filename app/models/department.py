"""
组织架构模型：Department
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Text
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin


class Department(SoftDeleteMixin, Base):
    """院系表"""
    __tablename__ = "department"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(100), nullable=False, comment="院系名称")
    code = Column(String(50), unique=True, nullable=False, comment="院系代码")
    description = Column(Text, nullable=True, comment="院系简介")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=正常 0=停用")

    # relationships
    clazzes = relationship("Clazz", back_populates="department")
    teachers = relationship("Teacher", back_populates="department")
    courses = relationship("Course", back_populates="department")
