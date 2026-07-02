"""
应用日志配置
- 按日轮转（TimedRotatingFileHandler）
- 保留 30 天
- 控制台 + 文件双输出
- 日志格式：[时间] [级别] [模块] [request_id] 消息
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler

from app.config import settings


class RequestIDFilter(logging.Filter):
    """为日志添加 request_id"""
    def filter(self, record):
        record.request_id = getattr(record, "request_id", "-")
        return True


def setup_logging():
    """初始化应用日志"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 日志格式
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)-15s] [%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 请求 ID 过滤器
    request_id_filter = RequestIDFilter()

    # 文件处理器（按日轮转）
    file_handler = TimedRotatingFileHandler(
        filename=settings.LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=settings.LOG_MAX_DAYS,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(request_id_filter)
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(fmt)
    console_handler.addFilter(request_id_filter)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 降低 SQLAlchemy 的日志级别（避免大量 SQL 输出）
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)

    logging.getLogger("app").info("日志系统初始化完成")
