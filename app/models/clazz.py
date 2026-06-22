"""
组织架构模型：Clazz
"""
from sqlalchemy import Column, Integer, String, SmallInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin


class Clazz(SoftDeleteMixin, Base):
    """班级表"""
    __tablename__ = "clazz"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(50), nullable=False, comment="班级名称")
    code = Column(String(50), unique=True, nullable=False, comment="班级代码")
    department_id = Column(Integer, ForeignKey("department.id"), nullable=False, comment="所属院系")
    grade = Column(String(10), nullable=False, comment="年级")
    counselor_id = Column(Integer, ForeignKey("teacher.id"), nullable=True, comment="辅导员")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=正常 0=停用")

    # relationships
    department = relationship("Department", back_populates="clazzes")
    counselor = relationship("Teacher", foreign_keys=[counselor_id], back_populates="counselor_clazzes")
    students = relationship("Student", back_populates="clazz")
    teacher_clazzes = relationship("TeacherClazz", back_populates="clazz", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="clazz")
