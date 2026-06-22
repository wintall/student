"""
导出所有 ORM 模型
"""
from app.models.base import Base, TimestampMixin, SoftDeleteMixin

# RBAC 权限体系
from app.models.user import User, Role, Menu, UserRole, RoleMenu, OperationLog

# 组织架构
from app.models.department import Department
from app.models.clazz import Clazz
from app.models.teacher import Teacher, TeacherClazz

# 教学管理
from app.models.student import Student, StudentCourse
from app.models.course import Course

# 考试与成绩
from app.models.exam import Exam
from app.models.score import Score

# 公告模块
from app.models.announcement import Announcement, AnnouncementRead

# 邮件系统
from app.models.email import EmailMessage, EmailAttachment

__all__ = [
    "Base", "TimestampMixin", "SoftDeleteMixin",
    "User", "Role", "Menu", "UserRole", "RoleMenu", "OperationLog",
    "Department", "Clazz", "Teacher", "TeacherClazz",
    "Student", "StudentCourse", "Course",
    "Exam", "Score",
    "Announcement", "AnnouncementRead",
    "EmailMessage", "EmailAttachment",
]
