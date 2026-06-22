"""
汇总注册所有子路由
"""
from fastapi import APIRouter

from app.api.v1.common import router as common_router
from app.api.v1.auth import router as auth_router
from app.api.v1.user import router as user_router
from app.api.v1.role import router as role_router
from app.api.v1.department import router as department_router
from app.api.v1.clazz import router as clazz_router
from app.api.v1.teacher import router as teacher_router
from app.api.v1.student import router as student_router
from app.api.v1.course import router as course_router
from app.api.v1.exam import router as exam_router
from app.api.v1.score import router as score_router
from app.api.v1.announcement import router as announcement_router
from app.api.v1.email import router as email_router
from app.api.v1.ai import router as ai_router
from app.api.v1.rag import router as rag_router

api_router = APIRouter()

api_router.include_router(common_router)
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(role_router)
api_router.include_router(department_router)
api_router.include_router(clazz_router)
api_router.include_router(teacher_router)
api_router.include_router(student_router)
api_router.include_router(course_router)
api_router.include_router(exam_router)
api_router.include_router(score_router)
api_router.include_router(announcement_router)
api_router.include_router(email_router)
api_router.include_router(ai_router)
api_router.include_router(rag_router)
