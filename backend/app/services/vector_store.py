"""PostgreSQL + pgvector知识索引持久化与向量检索。"""
import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from sqlalchemy import text

from app.db.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.utils.logger import logger


@dataclass(frozen=True)
class VectorSearchResult:
    content: str
    source: str
    similarity: float


class PostgresVectorStore:
    """负责增量建索引，并在PostgreSQL内执行余弦相似度检索。"""

    _fingerprints: Dict[str, str] = {}
    _process_lock = threading.Lock()

    def __init__(self, settings, client, knowledge_dir: Path):
        self.client = client
        self.knowledge_dir = knowledge_dir
        self.embedding_model = settings.RAG_EMBEDDING_MODEL
        self.embedding_dimensions = settings.RAG_EMBEDDING_DIMENSIONS
        if self.embedding_dimensions <= 0 or self.embedding_dimensions > 2000:
            raise ValueError("HNSW vector索引要求RAG_EMBEDDING_DIMENSIONS在1到2000之间")
        self.chunk_size = settings.RAG_CHUNK_SIZE
        self.chunk_overlap = settings.RAG_CHUNK_OVERLAP
        self.batch_size = settings.RAG_EMBEDDING_BATCH_SIZE

    def synchronize(self, files: List[Path], chunk_loader: Callable[[Path], List[str]]) -> None:
        """把本地知识文件增量同步到PostgreSQL，未变化文件不重复生成向量。"""
        fingerprint = self._files_fingerprint(files)
        cache_key = (
            f"{self.knowledge_dir}|{self.embedding_model}|{self.embedding_dimensions}|"
            f"{self.chunk_size}|{self.chunk_overlap}"
        )
        with self._process_lock:
            if (
                self._fingerprints.get(cache_key) == fingerprint
                and self._index_matches_files(files)
            ):
                return
            self._synchronize_locked(files, chunk_loader)
            self._fingerprints[cache_key] = fingerprint

    def _synchronize_locked(self, files: List[Path], chunk_loader: Callable[[Path], List[str]]) -> None:
        db = SessionLocal()
        try:
            # 跨进程锁：多个Celery Worker同时启动时，只允许一个Worker更新知识索引。
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
                {"lock_name": "qe_helper_knowledge_index"},
            )
            existing = {doc.source: doc for doc in db.query(KnowledgeDocument).all()}
            current_sources = {
                path.relative_to(self.knowledge_dir).as_posix() for path in files
            }

            for source, document in existing.items():
                if source not in current_sources:
                    db.delete(document)

            indexed_files = 0
            indexed_chunks = 0
            for path in files:
                source = path.relative_to(self.knowledge_dir).as_posix()
                stat = path.stat()
                content_hash = self._file_hash(path)
                document = existing.get(source)
                unchanged = document and all([
                    document.content_hash == content_hash,
                    document.embedding_model == self.embedding_model,
                    document.embedding_dimensions == self.embedding_dimensions,
                    document.chunk_size == self.chunk_size,
                    document.chunk_overlap == self.chunk_overlap,
                ])
                if unchanged:
                    document.file_modified_ns = stat.st_mtime_ns
                    document.file_size = stat.st_size
                    continue

                texts = chunk_loader(path)
                vectors = self._embed_batches(texts)
                if document is None:
                    document = KnowledgeDocument(
                        source=source,
                        content_hash=content_hash,
                        file_modified_ns=stat.st_mtime_ns,
                        file_size=stat.st_size,
                        embedding_model=self.embedding_model,
                        embedding_dimensions=self.embedding_dimensions,
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        chunk_count=len(texts),
                    )
                    db.add(document)
                    db.flush()
                else:
                    db.query(KnowledgeChunk).filter(
                        KnowledgeChunk.document_id == document.id
                    ).delete(synchronize_session=False)

                document.content_hash = content_hash
                document.file_modified_ns = stat.st_mtime_ns
                document.file_size = stat.st_size
                document.embedding_model = self.embedding_model
                document.embedding_dimensions = self.embedding_dimensions
                document.chunk_size = self.chunk_size
                document.chunk_overlap = self.chunk_overlap
                document.chunk_count = len(texts)
                db.add_all([
                    KnowledgeChunk(
                        document_id=document.id,
                        chunk_index=index,
                        content=content,
                        embedding=embedding,
                    )
                    for index, (content, embedding) in enumerate(zip(texts, vectors))
                ])
                indexed_files += 1
                indexed_chunks += len(texts)

            db.commit()
            logger.info(
                "PostgreSQL知识索引同步完成: 更新%s个文件, 写入%s个Chunk",
                indexed_files, indexed_chunks,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def search(
        self, query_vector: Sequence[float], top_k: int, routed_source: Optional[str] = None
    ) -> List[VectorSearchResult]:
        """使用pgvector的cosine distance和HNSW索引执行Top-K检索。"""
        self._validate_vector(query_vector)
        db = SessionLocal()
        try:
            distance = KnowledgeChunk.embedding.cosine_distance(list(query_vector))
            query = (
                db.query(KnowledgeChunk, KnowledgeDocument.source, distance.label("distance"))
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .filter(
                    KnowledgeDocument.embedding_model == self.embedding_model,
                    KnowledgeDocument.embedding_dimensions == self.embedding_dimensions,
                    KnowledgeDocument.chunk_size == self.chunk_size,
                    KnowledgeDocument.chunk_overlap == self.chunk_overlap,
                )
            )
            if routed_source:
                matched_source = self.resolve_source(routed_source, db=db)
                if not matched_source:
                    return []
                query = query.filter(KnowledgeDocument.source == matched_source)
            rows = query.order_by(distance).limit(top_k).all()
            return [
                VectorSearchResult(
                    content=chunk.content,
                    source=source,
                    similarity=max(-1.0, min(1.0, 1.0 - float(distance_value))),
                )
                for chunk, source, distance_value in rows
            ]
        finally:
            db.close()

    def has_chunks(self) -> bool:
        db = SessionLocal()
        try:
            return (
                db.query(KnowledgeChunk.id)
                .join(KnowledgeDocument)
                .filter(
                    KnowledgeDocument.embedding_model == self.embedding_model,
                    KnowledgeDocument.embedding_dimensions == self.embedding_dimensions,
                    KnowledgeDocument.chunk_size == self.chunk_size,
                    KnowledgeDocument.chunk_overlap == self.chunk_overlap,
                )
                .first()
                is not None
            )
        finally:
            db.close()

    def source_exists(self, routed_source: str) -> bool:
        return self.resolve_source(routed_source) is not None

    def resolve_source(self, routed_source: str, db=None) -> Optional[str]:
        owns_session = db is None
        db = db or SessionLocal()
        try:
            routed = routed_source.replace("\\", "/").casefold()
            sources = [
                row[0]
                for row in db.query(KnowledgeDocument.source).filter(
                    KnowledgeDocument.embedding_model == self.embedding_model,
                    KnowledgeDocument.embedding_dimensions == self.embedding_dimensions,
                    KnowledgeDocument.chunk_size == self.chunk_size,
                    KnowledgeDocument.chunk_overlap == self.chunk_overlap,
                ).all()
            ]
            for source in sources:
                normalized = source.replace("\\", "/").casefold()
                if normalized == routed or Path(normalized).name == Path(routed).name:
                    return source
            return None
        finally:
            if owns_session:
                db.close()

    def _index_matches_files(self, files: List[Path]) -> bool:
        """进程缓存命中时仍校验数据库，避免数据库重建后错误跳过同步。"""
        expected_sources = {
            path.relative_to(self.knowledge_dir).as_posix() for path in files
        }
        db = SessionLocal()
        try:
            documents = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.embedding_model == self.embedding_model,
                KnowledgeDocument.embedding_dimensions == self.embedding_dimensions,
                KnowledgeDocument.chunk_size == self.chunk_size,
                KnowledgeDocument.chunk_overlap == self.chunk_overlap,
            ).all()
            if {document.source for document in documents} != expected_sources:
                return False
            expected_chunks = sum(document.chunk_count for document in documents)
            actual_chunks = (
                db.query(KnowledgeChunk.id)
                .join(KnowledgeDocument)
                .filter(
                    KnowledgeDocument.embedding_model == self.embedding_model,
                    KnowledgeDocument.embedding_dimensions == self.embedding_dimensions,
                    KnowledgeDocument.chunk_size == self.chunk_size,
                    KnowledgeDocument.chunk_overlap == self.chunk_overlap,
                )
                .count()
            )
            return actual_chunks == expected_chunks
        finally:
            db.close()

    def _embed_batches(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            embedded = self.client.embed(batch, self.embedding_model)
            if len(embedded) != len(batch):
                raise ValueError("Embedding接口返回数量与请求文本数量不一致")
            for vector in embedded:
                self._validate_vector(vector)
            vectors.extend(embedded)
        return vectors

    def _validate_vector(self, vector: Sequence[float]) -> None:
        if len(vector) != self.embedding_dimensions:
            raise ValueError(
                f"Embedding维度为{len(vector)}，配置要求{self.embedding_dimensions}。"
                "请检查RAG_EMBEDDING_MODEL和RAG_EMBEDDING_DIMENSIONS"
            )

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _files_fingerprint(files: List[Path]) -> str:
        digest = hashlib.sha256()
        for path in files:
            stat = path.stat()
            digest.update(f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode())
        return digest.hexdigest()
