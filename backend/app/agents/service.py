"""多 Agent 版 RAG 服务。

``MultiAgentRAGService`` 继承 ``RAGService``，复用其知识库解析、分块、pgvector
索引同步与检索基础设施，只把 ``answer()`` 中的“单 Agent 循环”替换为
“主 Agent 编排 + 子 Agent 权限隔离”。对 ``AnswerService`` 而言是即插即用的。
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from app.agents.models import EvidenceItem, SearchObservation
from app.agents.orchestrator import OrchestratorAgent
from app.services.rag_service import RAGResult, RAGService
from app.utils.logger import logger


@dataclass(frozen=True)
class OrchestratedResult(RAGResult):
    """在 RAGResult 基础上附带编排轨迹，便于写入任务日志。"""

    trace: Tuple[str, ...] = ()


class RAGBackend:
    """把 RAGService 的检索与对话能力封装为主 Agent 专用的底层接口。

    只有主 Agent 持有该对象；子 Agent 拿到的是被 ScopedToolbox 包装、
    并已绑定检索范围的闭包，接触不到客户端或向量库。
    """

    def __init__(self, service: RAGService) -> None:
        self._service = service

    def search(self, query: str, routed_source: Optional[str]) -> SearchObservation:
        service = self._service
        query_vector = service.client.embed([query], service.embedding_model)[0]
        results = service.vector_store.search(query_vector, service.top_k, routed_source=routed_source)
        items = tuple(
            # 命中来源规则时，来源统一展示为规则指定的文件名（与单 Agent 版本一致）。
            EvidenceItem(routed_source or result.source, result.similarity, result.content)
            for result in results
            if result.similarity >= service.threshold
        )
        note = "" if items else "没有达到相关度阈值的知识"
        return SearchObservation(query, items, note)

    def chat(self, messages: list) -> str:
        service = self._service
        # 不传 tools：带大模型的子 Agent 没有任何工具可调用。
        message = service.client.complete(messages, service.chat_model, service.temperature)
        return (message.get("content") or "").strip()


class MultiAgentRAGService(RAGService):
    """主 Agent 编排检索 / 评估 / 答案生成三个子 Agent 的 RAG 服务。"""

    def __init__(self, settings, client=None, vector_store=None):
        super().__init__(settings, client=client, vector_store=vector_store)
        self.orchestrator = OrchestratorAgent(
            RAGBackend(self),
            threshold=self.threshold,
            max_iterations=self.max_iterations,
            # 多轮检索合并后最多交给答案 Agent 的证据条数。
            evidence_limit=self.top_k * 2,
        )

    def answer(self, question: str, language: str) -> Optional[RAGResult]:
        self._synchronize_index()
        if not self.vector_store.has_chunks():
            logger.warning("知识库为空: %s", self.knowledge_dir)
            return None

        source_rule = self.source_resolver.resolve(question) if self.source_resolver else None
        if source_rule and not self.vector_store.source_exists(source_rule.source):
            # 与单 Agent 版本一致：不拿其他文件冒充来源，按“未检索到”处理。
            logger.warning("来源映射指定的文件不在知识库索引中: %s", source_rule.source)
            return None

        outcome = self.orchestrator.run(question, language, source_rule)
        logger.info("多Agent编排轨迹: %s", " | ".join(outcome.trace))
        if outcome.answer is None:
            return None
        return OrchestratedResult(
            outcome.answer,
            outcome.similarity,
            list(outcome.sources),
            outcome.iterations,
            list(outcome.search_queries),
            source_rule.keyword if source_rule else None,
            outcome.trace,
        )
