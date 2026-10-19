"""基于知识库检索增强生成（RAG）的答案服务。"""
from typing import Optional, Tuple

from app.agents.service import MultiAgentRAGService
from app.config import settings
from app.services.rag_service import RAGService
from app.utils.logger import logger, log_to_database


class AnswerService:
    """为 Excel 中的问题检索知识库并生成答案。"""

    def __init__(self, max_score: float, language: str = "简体中文"):
        self.max_score = max_score
        self.language = language
        # 默认使用多 Agent 编排（主 Agent 路由 + 子 Agent 权限隔离）；
        # 设置 RAG_MULTI_AGENT_ENABLED=false 可回退到原来的单 Agent 循环。
        rag_class = MultiAgentRAGService if getattr(settings, "RAG_MULTI_AGENT_ENABLED", True) else RAGService
        self.rag = rag_class(settings)

    def generate_answer(
        self, question: str, task_id: str
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """返回 RAG 答案、相关度分数和用于回填的来源文件。"""
        try:
            result = self.rag.answer(question, self.language)
            if result is None:
                log_to_database(task_id, "INFO", "AnswerService", "知识库中未检索到相关内容", f"问题: {question[:100]}")
                return None, None, None

            score = round(max(0.0, min(1.0, result.similarity)) * self.max_score, 2)
            sources = ", ".join(result.sources)
            queries = " | ".join(result.search_queries)
            route = result.source_rule_keyword or "未命中规则"
            trace = " >> ".join(getattr(result, "trace", ()))
            mode = "多Agent编排" if isinstance(self.rag, MultiAgentRAGService) else "Agent Loop"
            details = (
                f"问题: {question[:100]}, 分数: {score}, 循环: {result.iterations}, "
                f"检索: {queries}, 来源规则: {route}, 来源: {sources}"
            )
            if trace:
                details += f", 编排轨迹: {trace[:1000]}"
            log_to_database(task_id, "INFO", "AnswerService", f"{mode}答案生成成功", details)
            return result.answer, score, "; ".join(result.sources)
        except Exception as exc:
            logger.exception("RAG答案生成失败: %s", exc)
            log_to_database(task_id, "ERROR", "AnswerService", "RAG答案生成失败", str(exc))
            return None, None, None
