"""
教学管理模型：Student, StudentCourse
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Student(SoftDeleteMixin, Base):
    """学生表 - 不含phone/email，统一在User表"""
    __tablename__ = "student"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), unique=True, nullable=False, comment="关联登录账号")
    student_no = Column(String(30), unique=True, nullable=False, comment="学号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(SmallInteger, nullable=False, comment="1=男 2=女")
    id_card = Column(String(18), unique=True, nullable=False, comment="身份证号")
    clazz_id = Column(Integer, ForeignKey("clazz.id"), nullable=False, comment="所属班级")
    enrollment_date = Column(Date, nullable=True, comment="入学日期")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=在读 2=休学 3=毕业 0=退学")

    # relationships
    user = relationship("User", back_populates="student")
    clazz = relationship("Clazz", back_populates="students")
    student_courses = relationship("StudentCourse", back_populates="student", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="student")


class StudentCourse(TimestampMixin, Base):
    """学生-课程选课表（多对多）"""
    __tablename__ = "student_course"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_course"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    student_id = Column(Integer, ForeignKey("student.id"), nullable=False, comment="学生ID")
    course_id = Column(Integer, ForeignKey("course.id"), nullable=False, comment="课程ID")
    select_time = Column(DateTime, nullable=False, comment="选课时间")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=已选 2=已退课")

    student = relationship("Student", back_populates="student_courses")
    course = relationship("Course", back_populates="student_courses")
