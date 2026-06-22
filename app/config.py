"""
应用配置模块 - 读取 .env 环境变量
"""
import json
import os
from typing import List, Union
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
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_DAYS: int = 30

    # ---- 密码策略 ----
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_USER_PASSWORD: str = "123456Ab"

    # ---- SMTP ----
    SMTP_HOST: str = "smtp.163.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_FROM_NAME: str = "学生信息管理系统"

    # ---- DeepSeek ----
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ---- 百度地图 ----
    BAIDU_MAP_KEY: str = ""
    BAIDU_MAP_IP_URL: str = "https://api.map.baidu.com/location/ip"

    # ---- 文件上传 ----
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 52428800  # 50MB

    @property
    def ABS_UPLOAD_DIR(self) -> str:
        """上传目录的绝对路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, self.UPLOAD_DIR)

    @property
    def ATTACHMENT_DIR(self) -> str:
        """邮件附件目录"""
        return os.path.join(self.ABS_UPLOAD_DIR, "email_attachments")

    # ---- RAG / 向量检索 ----
    # Embedding 模型：默认本地 m3e-base（纯免费，中文效果好；首次运行自动下载）
    # 如网络不通可切换到 text2vec-base-chinese（备选），或改为 external 使用第三方 API
    RAG_EMBEDDING_MODEL: str = "moka-ai/m3e-base"
    RAG_VECTOR_DIM: int = 768
    # 每段最大字符数（超出自动切分）；两段之间保留 overlap 以保持上下文
    RAG_CHUNK_SIZE: int = 220
    RAG_CHUNK_OVERLAP: int = 40
    # 向量搜索默认参数
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float = 0.45
    # Milvus 连接配置
    RAG_MILVUS_URI: str = "http://127.0.0.1:19530"
    RAG_MILVUS_COLLECTION: str = "sic_rag_four_books_v1"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# 全局单例
settings = Settings()
