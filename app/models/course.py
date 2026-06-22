"""
教学管理模型：Course
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin


class Course(SoftDeleteMixin, Base):
    """课程表"""
    __tablename__ = "course"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(100), nullable=False, comment="课程名称")
    code = Column(String(50), unique=True, nullable=False, comment="课程代码")
    credit = Column(Numeric(3, 1), nullable=False, comment="学分")
    hours = Column(Integer, nullable=False, comment="学时")
    course_type = Column(SmallInteger, nullable=False, comment="1=必修 2=选修 3=公共课")
    department_id = Column(Integer, ForeignKey("department.id"), nullable=False, comment="开设院系")
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True, comment="授课教师")
    description = Column(Text, nullable=True, comment="课程简介")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=正常 0=停用")

    # relationships
    department = relationship("Department", back_populates="courses")
    teacher = relationship("Teacher", back_populates="courses")
    student_courses = relationship("StudentCourse", back_populates="course")
    exams = relationship("Exam", back_populates="course")
    scores = relationship("Score", back_populates="course")
