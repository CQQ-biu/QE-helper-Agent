"""主 Agent：编排并路由子 Agent，发放权限，并在代码层做最终证据校验。

编排流程（每个 Excel 问题一次）::

    问题 ──► 路由(来源规则→锁定检索范围)
             │
             ▼
        ┌─► retriever 检索 ──► evaluator 评估证据
        │                        │ 不足且有新查询
        └────────────────────────┘
             │ 证据充分 / 达到轮数上限 / 无新查询
             ▼
        代码校验：必须存在达到阈值的真实证据 ──► answerer 生成答案 ──► 输出

路由与权限都由主 Agent 持有：子 Agent 不能决定下一步调谁，也不能改变检索范围。
"""
from typing import Any, List, Optional, Protocol, Sequence, Tuple

from app.agents.models import EvidenceItem, OrchestrationOutcome, SearchObservation
from app.agents.permissions import AuditLog, Capability, ScopedToolbox
from app.agents.subagents import AnswerAgent, EvaluatorAgent, RetrieverAgent

NO_ANSWER_MARKERS = {"", "未检索到", "not found"}


class AgentBackend(Protocol):
    """主 Agent 依赖的底层能力。只有主 Agent 持有它，子 Agent 只能拿到绑定后的闭包。"""

    def search(self, query: str, routed_source: Optional[str]) -> SearchObservation:
        ...

    def chat(self, messages: list) -> str:
        ...


class OrchestratorAgent:
    """主 Agent（编排 + 路由 + 权限发放 + 最终校验）。"""

    def __init__(
        self,
        backend: AgentBackend,
        threshold: float,
        max_iterations: int,
        evidence_limit: int,
        retriever: Optional[RetrieverAgent] = None,
        evaluator: Optional[EvaluatorAgent] = None,
        answerer: Optional[AnswerAgent] = None,
    ) -> None:
        if max_iterations <= 0:
            raise ValueError("max_iterations 必须大于0")
        if evidence_limit <= 0:
            raise ValueError("evidence_limit 必须大于0")
        self.backend = backend
        self.threshold = threshold
        self.max_iterations = max_iterations
        self.evidence_limit = evidence_limit
        self.retriever = retriever or RetrieverAgent()
        self.evaluator = evaluator or EvaluatorAgent()
        self.answerer = answerer or AnswerAgent()

    def run(self, question: str, language: str, source_rule: Any = None) -> OrchestrationOutcome:
        """编排一个问题。source_rule 需具备 .source 与 .keyword 属性（即 SourceRule）。"""
        question = (question or "").strip()
        trace: List[str] = []
        audit = AuditLog()
        if not question:
            return self._finish(None, 0.0, (), 0, (), trace, audit, "问题为空，直接返回未检索到")

        # —— 路由：来源规则命中时，检索范围由主 Agent 锁定到指定文件 ——
        routed_source = source_rule.source if source_rule else None
        if source_rule:
            trace.append(f"route: 命中来源规则“{source_rule.keyword}”，检索范围锁定到 {routed_source}")
        else:
            trace.append("route: 未命中来源规则，使用全库向量检索")

        # —— 权限：每个子 Agent 只拿到自己的工具箱，作用域在这里绑定 ——
        retriever_box = ScopedToolbox(
            self.retriever.policy({Capability.KNOWLEDGE_SEARCH: self.max_iterations}),
            {Capability.KNOWLEDGE_SEARCH: lambda query: self.backend.search(query, routed_source)},
            audit,
        )
        evaluator_box = ScopedToolbox(
            self.evaluator.policy({Capability.LLM_CHAT: self.max_iterations}),
            {Capability.LLM_CHAT: self.backend.chat},
            audit,
        )
        answerer_box = ScopedToolbox(
            self.answerer.policy({Capability.LLM_CHAT: 1}),
            {Capability.LLM_CHAT: self.backend.chat},
            audit,
        )

        # —— 检索 / 评估循环 ——
        observations: List[SearchObservation] = []
        queries: List[str] = []
        query = question
        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            observation = self.retriever.run(retriever_box, query)
            observations.append(observation)
            queries.append(observation.query)
            trace.append(
                f"[{iterations}] retriever: 查询“{observation.query}” → 命中 {len(observation.items)} 条，"
                f"最高相似度 {observation.best_similarity:.4f}"
            )
            if iterations >= self.max_iterations:
                trace.append(f"[{iterations}] 达到最大检索轮数，停止检索")
                break

            verdict = self.evaluator.run(evaluator_box, question, observations)
            trace.append(
                f"[{iterations}] evaluator: sufficient={verdict.sufficient}，理由：{verdict.reason or '无'}"
            )
            if verdict.sufficient:
                break
            next_query = verdict.rewritten_query
            if not next_query or next_query in queries:
                trace.append(f"[{iterations}] evaluator 未给出新的检索词，停止检索")
                break
            query = next_query

        # —— 代码层校验：没有达到阈值的真实证据时，绝不让模型作答 ——
        evidence = self._merge_evidence(observations)
        if not evidence:
            return self._finish(
                None, 0.0, (), iterations, tuple(queries), trace, audit,
                "没有达到相似度阈值的证据，不调用 answerer，返回未检索到",
            )

        answer = self.answerer.run(answerer_box, question, language, evidence)
        if answer.rstrip("。.").strip().lower() in NO_ANSWER_MARKERS:
            return self._finish(
                None, evidence[0].similarity, (), iterations, tuple(queries), trace, audit,
                "answerer 判定证据不足，返回未检索到",
            )

        sources = (routed_source,) if routed_source else tuple(dict.fromkeys(item.source for item in evidence))
        return self._finish(
            answer, evidence[0].similarity, sources, iterations, tuple(queries), trace, audit,
            f"answerer 基于 {len(evidence)} 条证据生成答案",
        )

    def _merge_evidence(self, observations: Sequence[SearchObservation]) -> Tuple[EvidenceItem, ...]:
        """合并多轮检索结果：去重、再次按阈值过滤、按相似度降序并限量。"""
        seen = set()
        items: List[EvidenceItem] = []
        for observation in observations:
            for item in observation.items:
                key = (item.source, item.content)
                if item.similarity < self.threshold or key in seen:
                    continue
                seen.add(key)
                items.append(item)
        items.sort(key=lambda item: -item.similarity)
        return tuple(items[: self.evidence_limit])

    @staticmethod
    def _finish(
        answer: Optional[str],
        similarity: float,
        sources: Tuple[str, ...],
        iterations: int,
        queries: Tuple[str, ...],
        trace: List[str],
        audit: AuditLog,
        summary: str,
    ) -> OrchestrationOutcome:
        trace.append(f"result: {summary}")
        trace.append(f"audit: 授权调用 {audit.allowed_count()} 次，拒绝 {len(audit.denied())} 次")
        return OrchestrationOutcome(answer, similarity, sources, iterations, queries, tuple(trace))
