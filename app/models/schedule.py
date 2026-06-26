"""
Academic calendar, classroom and timetable models.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin


class Term(SoftDeleteMixin, Base):
    """Academic term."""
    __tablename__ = "term"
    __table_args__ = (
        UniqueConstraint("academic_year", "semester", name="uq_term_year_semester"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    name = Column(String(100), nullable=False, comment="Term name")
    academic_year = Column(String(20), nullable=False, comment="Academic year")
    semester = Column(SmallInteger, nullable=False, comment="Semester number")
    start_date = Column(Date, nullable=False, comment="Start date")
    end_date = Column(Date, nullable=False, comment="End date")
    week_count = Column(Integer, nullable=False, comment="Teaching week count")
    is_current = Column(Boolean, default=False, nullable=False, comment="Current term")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=enabled 0=disabled")
    remark = Column(Text, nullable=True, comment="Remark")

    schedules = relationship("CourseSchedule", back_populates="term")


class TermEvent(SoftDeleteMixin, Base):
    """Teaching calendar event."""
    __tablename__ = "term_event"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    term_id = Column(Integer, ForeignKey("term.id"), nullable=False, comment="Term ID")
    event_type = Column(String(30), nullable=False, comment="holiday/exam/weekend_adjust/notice/other")
    title = Column(String(100), nullable=False, comment="Event title")
    start_date = Column(Date, nullable=False, comment="Start date")
    end_date = Column(Date, nullable=False, comment="End date")
    is_teaching_day = Column(Boolean, default=False, nullable=False, comment="Teaching day")
    description = Column(Text, nullable=True, comment="Description")

    term = relationship("Term")


class Classroom(SoftDeleteMixin, Base):
    """Classroom."""
    __tablename__ = "classroom"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    name = Column(String(100), nullable=False, unique=True, comment="Classroom name")
    building = Column(String(100), nullable=True, comment="Building")
    room_no = Column(String(50), nullable=True, comment="Room number")
    campus = Column(String(100), nullable=True, comment="Campus")
    capacity = Column(Integer, nullable=False, default=0, comment="Capacity")
    room_type = Column(String(30), nullable=False, default="normal", comment="Room type")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=available 0=disabled 2=maintenance")
    remark = Column(Text, nullable=True, comment="Remark")

    schedules = relationship("CourseSchedule", back_populates="classroom")


class CourseSchedule(SoftDeleteMixin, Base):
    """Course timetable item."""
    __tablename__ = "course_schedule"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    term_id = Column(Integer, ForeignKey("term.id"), nullable=False, comment="Term ID")
    course_id = Column(Integer, ForeignKey("course.id"), nullable=False, comment="Course ID")
    clazz_id = Column(Integer, ForeignKey("clazz.id"), nullable=False, comment="Class ID")
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=False, comment="Teacher ID")
    classroom_id = Column(Integer, ForeignKey("classroom.id"), nullable=True, comment="Classroom ID")
    weekday = Column(SmallInteger, nullable=False, comment="Weekday 1-7")
    start_section = Column(SmallInteger, nullable=False, comment="Start section")
    end_section = Column(SmallInteger, nullable=False, comment="End section")
    start_week = Column(SmallInteger, nullable=False, comment="Start week")
    end_week = Column(SmallInteger, nullable=False, comment="End week")
    week_type = Column(String(10), nullable=False, default="all", comment="all/odd/even")
    schedule_type = Column(String(20), nullable=False, default="normal", comment="normal/makeup/temporary")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=normal 0=disabled")
    remark = Column(Text, nullable=True, comment="Remark")

    term = relationship("Term", back_populates="schedules")
    course = relationship("Course", back_populates="schedules")
    clazz = relationship("Clazz", back_populates="schedules")
    teacher = relationship("Teacher", back_populates="schedules")
    classroom = relationship("Classroom", back_populates="schedules")
