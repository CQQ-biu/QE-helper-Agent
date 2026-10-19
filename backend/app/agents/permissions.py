"""子 Agent 权限模型：能力白名单、调用额度与审计。

隔离原则：
1. 子 Agent 拿不到 LLM 客户端、向量库等底层对象，只能通过主 Agent 发放的
   ``ScopedToolbox`` 调用被授权的能力；
2. 每个能力绑定在主 Agent 构造的闭包里（例如检索范围已被锁定到来源规则指定的
   文件），子 Agent 无法修改；
3. 每项能力都有调用额度，防止失控循环；
4. 所有授权与拒绝都会写入审计日志。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Mapping


class Capability(str, Enum):
    """子 Agent 可被授予的能力。"""

    KNOWLEDGE_SEARCH = "knowledge:search"
    LLM_CHAT = "llm:chat"


class PermissionDeniedError(PermissionError):
    """Agent 调用了未授权的能力。"""


class BudgetExceededError(RuntimeError):
    """Agent 的某项能力调用次数超过额度。"""


@dataclass(frozen=True)
class AgentPolicy:
    """一个子 Agent 的权限策略。max_calls 中未列出的能力不限次数。"""

    agent: str
    capabilities: FrozenSet[Capability]
    max_calls: Mapping[Capability, int] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditEvent:
    agent: str
    action: str
    allowed: bool
    detail: str = ""


class AuditLog:
    """记录一次编排过程中所有能力调用（含被拒绝的）。"""

    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    def record(self, agent: str, action: str, allowed: bool, detail: str = "") -> None:
        self.events.append(AuditEvent(agent, action, allowed, detail))

    def denied(self) -> List[AuditEvent]:
        return [event for event in self.events if not event.allowed]

    def allowed_count(self) -> int:
        return sum(1 for event in self.events if event.allowed)


class ScopedToolbox:
    """发给单个子 Agent 的受限工具箱。

    handlers 由主 Agent 构造并已绑定作用域；工具箱只暴露策略白名单内的能力。
    """

    def __init__(
        self,
        policy: AgentPolicy,
        handlers: Mapping[Capability, Callable[..., Any]],
        audit: AuditLog,
    ) -> None:
        self.policy = policy
        # 即使主 Agent 误传了额外 handler，策略之外的能力也不会被保留。
        self._handlers: Dict[Capability, Callable[..., Any]] = {
            capability: handler
            for capability, handler in handlers.items()
            if capability in policy.capabilities
        }
        self._audit = audit
        self._used: Dict[Capability, int] = {}

    def invoke(self, capability: Capability, *args: Any, **kwargs: Any) -> Any:
        agent = self.policy.agent
        if capability not in self.policy.capabilities or capability not in self._handlers:
            self._audit.record(agent, capability.value, False, "未授权的能力")
            raise PermissionDeniedError(f"Agent“{agent}”无权使用 {capability.value}")

        limit = self.policy.max_calls.get(capability)
        used = self._used.get(capability, 0)
        if limit is not None and used >= limit:
            self._audit.record(agent, capability.value, False, f"超过调用额度 {limit}")
            raise BudgetExceededError(
                f"Agent“{agent}”对 {capability.value} 的调用次数已达上限 {limit}"
            )

        self._used[capability] = used + 1
        self._audit.record(agent, capability.value, True)
        return self._handlers[capability](*args, **kwargs)

    def search(self, query: str):
        """检索知识库（需要 knowledge:search）。"""
        return self.invoke(Capability.KNOWLEDGE_SEARCH, query)

    def chat(self, messages: list) -> str:
        """调用大模型对话，不带任何工具（需要 llm:chat）。"""
        return self.invoke(Capability.LLM_CHAT, messages)
