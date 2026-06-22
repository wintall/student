import os

files = {}

files['app/config.py'] = '''"""
应用配置模块 - 读取 .env 环境变量
"""
import json
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """应用配置"""

    # ---- 应用 ----
    APP_NAME: str = "学生信息管理系统"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = False

    # ---- 数据库 ----
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "student"
    DB_CHARSET: str = "utf8mb4"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset={self.DB_CHARSET}"
        )

    # ---- Redis ----
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ---- JWT ----
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- CORS ----
    CORS_ORIGINS: str = \'\'\'["http://localhost:5173","http://localhost:3000"]\'\'\'

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_DAYS: int = 30

    # ---- 密码策略 ----
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_USER_PASSWORD: str = "123456Ab"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# 全局单例
settings = Settings()
'''

files['app/database.py'] = '''"""
数据库引擎和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

# 创建引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.APP_DEBUG,
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

files['app/redis.py'] = '''"""
Redis 连接池和常用操作封装
"""
import redis
from app.config import settings

# Redis 连接池
_redis_pool = None


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


def get_redis() -> redis.Redis:
    """获取 Redis 客户端"""
    return redis.Redis(connection_pool=get_redis_pool())


# ---- 便捷操作 ----

def redis_set(key: str, value: str, ex: int = None):
    """设置键值，ex 为过期时间(秒)"""
    r = get_redis()
    if ex:
        r.set(key, value, ex=ex)
    else:
        r.set(key, value)


def redis_get(key: str):
    """获取值"""
    return get_redis().get(key)


def redis_delete(key: str):
    """删除键"""
    return get_redis().delete(key)


def redis_incr(key: str, ex: int = None) -> int:
    """自增计数器"""
    r = get_redis()
    val = r.incr(key)
    if ex and val == 1:
        r.expire(key, ex)
    return val


def redis_close():
    """关闭连接池"""
    global _redis_pool
    if _redis_pool:
        _redis_pool.disconnect()
        _redis_pool = None
'''

for filepath, content in files.items():
    full_path = os.path.join(r'e:\\student', filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Created: {filepath}')

print('Done!')
