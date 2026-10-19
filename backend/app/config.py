"""
配置文件
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL + pgvector：业务数据和知识向量统一存储
    DATABASE_URL: str = "postgresql+psycopg2://qe_helper:qe_helper@localhost:5432/qe_helper"
    
    # Redis配置（用于Celery）
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # 日志配置
    LOG_DIR: str = "./logs"
    LOG_LEVEL: str = "INFO"

    # RAG 配置（兼容 OpenAI API 协议）
    RAG_API_KEY: str = ""
    RAG_BASE_URL: str = "https://api.openai.com/v1"
    RAG_CHAT_MODEL: str = "gpt-4.1-mini"
    RAG_EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_EMBEDDING_DIMENSIONS: int = 1536
    RAG_KNOWLEDGE_BASE_DIR: str = "./knowledge_base"
    RAG_SOURCE_MAPPING_FILE: str = "./source_mapping.xlsx"
    RAG_TOP_K: int = 4
    RAG_SIMILARITY_THRESHOLD: float = 0.35
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 120
    RAG_EMBEDDING_BATCH_SIZE: int = 64
    RAG_TEMPERATURE: float = 0.1
    RAG_REQUEST_TIMEOUT: int = 60
    RAG_AGENT_MAX_ITERATIONS: int = 3
    # 多 Agent 编排（主 Agent 路由 + 子 Agent 权限隔离）；false 时回退到单 Agent 循环
    RAG_MULTI_AGENT_ENABLED: bool = True
    
    # API配置
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
