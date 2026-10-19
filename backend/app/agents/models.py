"""多 Agent 之间传递的不可变数据结构。

所有结构都是 frozen dataclass：子 Agent 只能读取、不能改写上游产出，
这是“数据隔离”的基础。
"""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class EvidenceItem:
    """一条达到相似度阈值的知识片段。"""

    source: str
    similarity: float
    content: str


@dataclass(frozen=True)
class SearchObservation:
    """一次知识库检索的结果。items 只包含达到阈值的片段。"""

    query: str
    items: Tuple[EvidenceItem, ...] = ()
    note: str = ""

    @property
    def found(self) -> bool:
        return bool(self.items)

    @property
    def best_similarity(self) -> float:
        return max((item.similarity for item in self.items), default=0.0)


@dataclass(frozen=True)
class Verdict:
    """证据评估 Agent 的结论。"""

    sufficient: bool
    reason: str = ""
    rewritten_query: Optional[str] = None


@dataclass(frozen=True)
class OrchestrationOutcome:
    """主 Agent 编排一个问题后的最终产出。answer 为 None 表示“未检索到”。"""

    answer: Optional[str]
    similarity: float
    sources: Tuple[str, ...]
    iterations: int
    search_queries: Tuple[str, ...]
    trace: Tuple[str, ...]
