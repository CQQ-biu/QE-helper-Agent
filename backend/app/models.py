"""
数据库模型
"""
from sqlalchemy import (
    BigInteger, Column, DateTime, Float, ForeignKey, Index, Integer, String,
    Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.config import settings
from app.db.database import Base


class TaskRecord(Base):
    """任务记录表"""
    __tablename__ = "task_records"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True, comment="Celery任务ID")
    customer_name = Column(String(200), comment="客户名称")
    customer_type = Column(String(50), comment="客户类型：设计公司/直接客户")
    work_number = Column(String(100), comment="工号")
    fill_date = Column(DateTime, comment="填表日期")
    answer_language = Column(String(50), comment="答案语言：简体中文/英语")
    max_score = Column(Float, comment="最高分数")
    status = Column(String(50), default="pending", comment="任务状态：pending/processing/completed/failed")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联关系
    files = relationship("ExcelFile", back_populates="task_record", cascade="all, delete-orphan")


class ExcelFile(Base):
    """Excel文件表"""
    __tablename__ = "excel_files"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("task_records.id"), comment="关联任务ID")
    file_name = Column(String(500), comment="原始文件名")
    file_path = Column(String(1000), comment="文件存储路径")
    file_size = Column(Integer, comment="文件大小（字节）")
    file_type = Column(String(50), default="original", comment="文件类型：original/processed")
    processed_file_path = Column(String(1000), comment="处理后的文件路径")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关联关系
    task_record = relationship("TaskRecord", back_populates="files")
    
    # Excel配置信息（JSON格式存储）
    excel_config = Column(Text, comment="Excel配置信息（JSON格式）")


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), index=True, comment="关联任务ID")
    level = Column(String(20), comment="日志级别：INFO/WARNING/ERROR")
    module = Column(String(100), comment="模块名称")
    message = Column(Text, comment="日志消息")
    details = Column(Text, comment="详细信息（JSON格式）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class KnowledgeDocument(Base):
    """已持久化到PostgreSQL的知识文件及其索引版本。"""
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True)
    source = Column(String(1000), nullable=False, unique=True, index=True, comment="知识库相对路径")
    content_hash = Column(String(64), nullable=False, comment="文件内容SHA-256")
    file_modified_ns = Column(BigInteger, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    embedding_model = Column(String(200), nullable=False)
    embedding_dimensions = Column(Integer, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    chunk_overlap = Column(Integer, nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0)
    indexed_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    chunks = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base):
    """知识文本块及pgvector向量。"""
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.RAG_EMBEDDING_DIMENSIONS), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")

