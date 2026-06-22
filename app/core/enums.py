"""
全局枚举定义
"""
from enum import IntEnum


class UserStatus(IntEnum):
    """用户状态"""
    ACTIVE = 1
    DISABLED = 0


class Gender(IntEnum):
    """性别"""
    MALE = 1
    FEMALE = 2


class MenuType(IntEnum):
    """菜单类型"""
    DIRECTORY = 1
    MENU = 2
    BUTTON = 3


class Status(IntEnum):
    """通用启用/停用"""
    ENABLED = 1
    DISABLED = 0


class StudentStatus(IntEnum):
    """学生状态"""
    ACTIVE = 1
    SUSPENDED = 2
    GRADUATED = 3
    DROPPED = 0


class TeacherStatus(IntEnum):
    """教职工状态"""
    ACTIVE = 1
    RESIGNED = 0


class CourseType(IntEnum):
    """课程类型"""
    REQUIRED = 1       # 必修
    ELECTIVE = 2       # 选修
    PUBLIC = 3         # 公共课


class ExamType(IntEnum):
    """考试类型"""
    MIDTERM = 1        # 期中
    FINAL = 2          # 期末
    RETAKE = 3         # 补考
    QUIZ = 4           # 测验


class StudentCourseStatus(IntEnum):
    """选课状态"""
    SELECTED = 1
    DROPPED = 2


class AnnouncementType(IntEnum):
    """公告类型"""
    NOTICE = 1         # 通知
    ACTIVITY = 2       # 活动
    URGENT = 3         # 紧急


class AnnouncementStatus(IntEnum):
    """公告状态"""
    PUBLISHED = 1
    DRAFT = 2
    WITHDRAWN = 0


# 枚举字典（供前端接口使用）
ENUM_DICT = {
    "user_status": [{"value": e.value, "label": e.name} for e in UserStatus],
    "gender": [{"value": e.value, "label": e.name} for e in Gender],
    "menu_type": [{"value": e.value, "label": e.name} for e in MenuType],
    "status": [{"value": e.value, "label": e.name} for e in Status],
    "student_status": [{"value": e.value, "label": e.name} for e in StudentStatus],
    "teacher_status": [{"value": e.value, "label": e.name} for e in TeacherStatus],
    "course_type": [{"value": e.value, "label": e.name} for e in CourseType],
    "exam_type": [{"value": e.value, "label": e.name} for e in ExamType],
    "announcement_type": [{"value": e.value, "label": e.name} for e in AnnouncementType],
    "announcement_status": [{"value": e.value, "label": e.name} for e in AnnouncementStatus],
}
