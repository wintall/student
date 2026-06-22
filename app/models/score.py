"""
考试与成绩模型：Score
"""
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin


class Score(SoftDeleteMixin, Base):
    """成绩表"""
    __tablename__ = "score"
    __table_args__ = (UniqueConstraint("student_id", "exam_id", name="uq_score_student_exam"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    student_id = Column(Integer, ForeignKey("student.id"), nullable=False, comment="学生ID")
    exam_id = Column(Integer, ForeignKey("exam.id"), nullable=False, comment="考试ID")
    course_id = Column(Integer, ForeignKey("course.id"), nullable=False, comment="课程ID(冗余)")
    score = Column(Numeric(5, 2), nullable=True, comment="分数")
    grade = Column(String(5), nullable=True, comment="等级A/B/C/D/F")
    rank_in_class = Column(Integer, nullable=True, comment="班级排名")
    remark = Column(String(255), nullable=True, comment="备注")
    scorer_id = Column(Integer, ForeignKey("teacher.id"), nullable=True, comment="录入人(教师)")

    # relationships
    student = relationship("Student", back_populates="scores")
    exam = relationship("Exam", back_populates="scores")
    course = relationship("Course", back_populates="scores")
    scorer = relationship("Teacher", back_populates="scores")
