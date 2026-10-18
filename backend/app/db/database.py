"""PostgreSQL数据库连接与pgvector初始化。"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


if not settings.DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    raise RuntimeError("本项目已启用pgvector，DATABASE_URL必须指向PostgreSQL")

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    """先启用vector扩展，再创建业务表与向量表。"""
    with engine.begin() as connection:
        # FastAPI和多个Celery子进程可能同时启动，用事务级锁串行化建表。
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('qe_helper_schema_init'))")
        )
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)


def get_db():
    """为FastAPI请求提供独立数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
