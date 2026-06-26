"""
Attendance management models.
"""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin


class AttendanceRecord(SoftDeleteMixin, Base):
    """Student/teacher attendance record."""
    __tablename__ = "attendance_record"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    person_type = Column(String(20), nullable=False, index=True, comment="student/teacher")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="User ID")
    student_id = Column(Integer, ForeignKey("student.id"), nullable=True, index=True, comment="Student ID")
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True, index=True, comment="Teacher ID")
    clazz_id = Column(Integer, ForeignKey("clazz.id"), nullable=True, index=True, comment="Class ID")
    department_id = Column(Integer, ForeignKey("department.id"), nullable=True, index=True, comment="Department ID")
    attendance_date = Column(Date, nullable=False, index=True, comment="Attendance date")
    period_type = Column(String(30), nullable=False, default="day", comment="day/morning/afternoon/course/custom")
    course_schedule_id = Column(Integer, ForeignKey("course_schedule.id"), nullable=True, index=True, comment="Course schedule ID")
    checkin_time = Column(DateTime, nullable=True, comment="Check-in time")
    checkout_time = Column(DateTime, nullable=True, comment="Check-out time")
    status = Column(String(30), nullable=False, default="normal", index=True, comment="normal/late/early_leave/absent/leave/official/holiday/manual")
    source = Column(String(30), nullable=False, default="manual", index=True, comment="manual/leave_sync/import/system")
    leave_request_id = Column(Integer, ForeignKey("leave_request.id"), nullable=True, index=True, comment="Leave request ID")
    remark = Column(String(500), nullable=True, comment="Remark")
    created_by = Column(Integer, ForeignKey("user.id"), nullable=True, comment="Creator")
    updated_by = Column(Integer, ForeignKey("user.id"), nullable=True, comment="Updater")

    user = relationship("User", foreign_keys=[user_id])
    student = relationship("Student")
    teacher = relationship("Teacher")
    clazz = relationship("Clazz")
    department = relationship("Department")
    course_schedule = relationship("CourseSchedule")
    leave_request = relationship("LeaveRequest")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
