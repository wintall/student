"""
考试与成绩模型：Exam
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Date, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin


class Exam(SoftDeleteMixin, Base):
    """考试表"""
    __tablename__ = "exam"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(100), nullable=False, comment="考试名称")
    course_id = Column(Integer, ForeignKey("course.id"), nullable=False, comment="关联课程")
    exam_type = Column(SmallInteger, nullable=False, comment="1=期中 2=期末 3=补考 4=测验")
    exam_date = Column(Date, nullable=False, comment="考试日期")
    exam_time = Column(String(50), nullable=True, comment="考试时间段")
    location = Column(String(100), nullable=True, comment="考试地点")
    clazz_id = Column(Integer, ForeignKey("clazz.id"), nullable=True, comment="参加班级(NULL=全院)")
    description = Column(Text, nullable=True, comment="备注")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=正常 0=取消")

    # relationships
    course = relationship("Course", back_populates="exams")
    clazz = relationship("Clazz", back_populates="exams")
    scores = relationship("Score", back_populates="exam")
