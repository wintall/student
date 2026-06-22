import os

files = {}

files['app/core/enums.py'] = '''"""
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
'''

files['main.py'] = '''"""
学生信息管理系统 - FastAPI 入口
"""
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.redis import redis_close


logger = logging.getLogger("app")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求 ID 追踪中间件"""
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    yield
    logger.info(f"{settings.APP_NAME} 关闭中...")
    redis_close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="学生信息管理系统后端 API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求 ID 中间件
app.add_middleware(RequestIDMiddleware)


# 注册路由（后续 Task 6 填充）
# from app.api.v1.router import api_router
# app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION}", "docs": "/api/docs"}
'''

for filepath, content in files.items():
    full_path = os.path.join(r'e:\\student', filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Created: {filepath}')

print('Done!')
