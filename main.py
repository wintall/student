"""
学生信息管理系统 - FastAPI 入口
"""
import os
import uuid
import sys
import ctypes
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.config import settings
from app.redis import redis_close
from app.exceptions import BusinessException


logger = logging.getLogger("app")


def configure_console_encoding():
    """Keep Windows console output readable for Chinese startup logs."""
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


configure_console_encoding()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求 ID 追踪中间件"""
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        import logging
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = request_id
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            logging.setLogRecordFactory(old_factory)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    from app.core.logging_config import setup_logging
    setup_logging()

    # 确保上传目录存在
    try:
        os.makedirs(settings.ATTACHMENT_DIR, exist_ok=True)
    except Exception:
        pass

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


# 挂载附件目录（用于下载邮件附件）
try:
    app.mount("/uploads", StaticFiles(directory=settings.ABS_UPLOAD_DIR), name="uploads")
except Exception:
    pass  # 目录不存在时忽略


# ---- 全局异常处理器 ----

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常处理"""
    return JSONResponse(
        status_code=200,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验异常处理"""
    errors = exc.errors()
    messages = []
    for err in errors:
        loc = err.get("loc", [])
        field = loc[-1] if loc else "未知字段"
        msg = err.get("msg", "")
        messages.append(f"{field}: {msg}")
    return JSONResponse(
        status_code=200,
        content={"code": 400, "message": "; ".join(messages), "data": None},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """数据库唯一约束冲突"""
    error_msg = str(exc.orig) if hasattr(exc, "orig") else "数据冲突"
    if "Duplicate entry" in error_msg:
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": "该数据已存在，请勿重复添加", "data": None},
        )
    return JSONResponse(
        status_code=200,
        content={"code": 400, "message": f"数据冲突: {error_msg}", "data": None},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """数据库异常处理"""
    logger.error(f"数据库异常: {exc}")
    return JSONResponse(
        status_code=200,
        content={"code": 500, "message": "数据库操作异常", "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未知异常处理"""
    logger.error(f"未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


# 注册路由
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION}", "docs": "/api/docs"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
