"""
组织架构模型：Teacher, TeacherClazz
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Teacher(SoftDeleteMixin, Base):
    """教职工表 - 不含phone/email，统一在User表"""
    __tablename__ = "teacher"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), unique=True, nullable=False, comment="关联登录账号")
    employee_no = Column(String(30), unique=True, nullable=False, comment="工号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(SmallInteger, nullable=False, comment="1=男 2=女")
    id_card = Column(String(18), unique=True, nullable=False, comment="身份证号")
    position = Column(String(50), nullable=False, comment="岗位")
    title = Column(String(50), nullable=True, comment="职称")
    department_id = Column(Integer, ForeignKey("department.id"), nullable=True, comment="所属院系")
    entry_date = Column(Date, nullable=True, comment="入职日期")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=在职 0=离职")

    # relationships
    user = relationship("User", back_populates="teacher")
    department = relationship("Department", back_populates="teachers")
    counselor_clazzes = relationship("Clazz", foreign_keys="Clazz.counselor_id", back_populates="counselor")
    teacher_clazzes = relationship("TeacherClazz", back_populates="teacher", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="teacher")
    scores = relationship("Score", back_populates="scorer")


class TeacherClazz(TimestampMixin, Base):
    """教师-班级关联表（多对多）"""
    __tablename__ = "teacher_clazz"
    __table_args__ = (UniqueConstraint("teacher_id", "clazz_id", name="uq_teacher_clazz"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=False, comment="教职工ID")
    clazz_id = Column(Integer, ForeignKey("clazz.id"), nullable=False, comment="班级ID")

    teacher = relationship("Teacher", back_populates="teacher_clazzes")
    clazz = relationship("Clazz", back_populates="teacher_clazzes")
