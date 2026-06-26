"""
请假模块模型：LeaveRequest
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin


class LeaveRequest(SoftDeleteMixin, Base):
    """请假申请表"""
    __tablename__ = "leave_request"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    applicant_user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="申请人用户ID")
    applicant_type = Column(String(20), nullable=False, index=True, comment="申请人类型: student/teacher")
    student_id = Column(Integer, ForeignKey("student.id"), nullable=True, index=True, comment="学生ID")
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True, index=True, comment="教职工ID")
    clazz_id = Column(Integer, ForeignKey("clazz.id"), nullable=True, index=True, comment="班级ID")
    department_id = Column(Integer, ForeignKey("department.id"), nullable=True, index=True, comment="院系ID")

    leave_type = Column(String(30), nullable=False, comment="请假类型")
    start_time = Column(DateTime, nullable=False, index=True, comment="开始时间")
    end_time = Column(DateTime, nullable=False, index=True, comment="结束时间")
    duration_hours = Column(Numeric(8, 2), nullable=False, comment="请假时长(小时)")
    reason = Column(Text, nullable=False, comment="请假原因")
    destination = Column(String(200), nullable=True, comment="去向/地点")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")
    emergency_contact = Column(String(100), nullable=True, comment="紧急联系人")
    attachment_url = Column(String(500), nullable=True, comment="证明材料")
    remark = Column(String(255), nullable=True, comment="备注")

    status = Column(String(20), default="pending", nullable=False, index=True, comment="状态")
    reviewer_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True, comment="审批人")
    reviewer_role = Column(String(50), nullable=True, comment="审批身份")
    review_comment = Column(String(500), nullable=True, comment="审批意见")
    reviewed_at = Column(DateTime, nullable=True, comment="审批时间")

    applicant = relationship("User", foreign_keys=[applicant_user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    student = relationship("Student")
    teacher = relationship("Teacher")
    clazz = relationship("Clazz")
    department = relationship("Department")
