# 多 Agent 版 RAG 问答

本文说明 `app/agents/` 的设计：**主 Agent 编排路由** + **子 Agent 权限隔离**。

## 架构

```
问题 ──► 主 Agent（OrchestratorAgent）
          │ 路由：命中来源规则 → 检索范围锁定到指定文件
          ▼
     ┌─► retriever（检索）──► evaluator（评估证据是否充分）
     │                           │ 不足且给出新查询词
     └───────────────────────────┘
          │ 证据充分 / 达到轮数上限 / 无新查询词
          ▼
     代码校验：必须存在达到相似度阈值的真实证据
          ▼
     answerer（只依据证据生成答案）──► 结果（附编排轨迹）
```

主 Agent 负责：路由决策、循环与轮数控制、发放子 Agent 的权限、合并证据、最终校验。
子 Agent 不能决定“下一步调谁”，也不能改变检索范围。

## 子 Agent 权限（最小权限）

| 子 Agent | 能力 | 能看到什么 | 不能做什么 |
|---|---|---|---|
| `retriever` | `knowledge:search` | 主 Agent 下发的查询词 | 调用大模型；改变检索范围 |
| `evaluator` | `llm:chat` | 问题 + 命中证据正文（不含来源文件名） | 检索；看到来源规则；回答问题 |
| `answerer` | `llm:chat` | 问题 + 语言 + 已确认证据 | 检索；再次改写查询 |

隔离是靠代码强制的，不是靠提示词约定：

- 子 Agent 拿不到 LLM 客户端和向量库，只能通过 `ScopedToolbox` 调用被授权的能力。
- 检索范围在主 Agent 构造工具箱时就绑定到闭包里，`retriever` 无法覆盖。
- 每项能力有调用额度（`retriever` 与 `evaluator` 每问最多 `RAG_AGENT_MAX_ITERATIONS` 次，`answerer` 最多 1 次）。
- 越权调用抛出 `PermissionDeniedError`，超额抛出 `BudgetExceededError`，并写入审计日志。
- 知识库内容视为不可信数据：唯一能调用工具的 `retriever` 不带大模型，带大模型的
  `evaluator` / `answerer` 没有任何工具，因此知识文本里夹带的指令无法触发检索或其他动作。

## 与原有行为保持一致

- 答案必须有达到 `RAG_SIMILARITY_THRESHOLD` 的真实检索证据，否则回填“未检索到”，且不会调用 `answerer`。
- 命中来源规则时，检索锁定到该文件，来源列回填规则指定的文件名；规则指定的文件不在索引中时按“未检索到”处理。
- `AnswerService` 的返回值（答案、分数、来源）不变。

## 配置

| 变量 | 默认 | 说明 |
|---|---|---|
| `RAG_MULTI_AGENT_ENABLED` | `true` | `false` 时回退到原单 Agent 循环（`RAGService`） |
| `RAG_AGENT_MAX_ITERATIONS` | `3` | 单个问题最多检索 / 评估的轮数，同时是子 Agent 的调用额度 |

## 代码结构

| 文件 | 作用 |
|---|---|
| `app/agents/orchestrator.py` | 主 Agent：编排、路由、发放权限、最终校验 |
| `app/agents/subagents.py` | `RetrieverAgent` / `EvaluatorAgent` / `AnswerAgent` |
| `app/agents/permissions.py` | `Capability`、`AgentPolicy`、`ScopedToolbox`、审计日志 |
| `app/agents/models.py` | 子 Agent 之间传递的不可变数据结构 |
| `app/agents/service.py` | `MultiAgentRAGService`：继承 `RAGService`，复用索引与检索基础设施 |

## 新增一个子 Agent

1. 在 `Capability` 中声明它需要的能力（如果现有能力不够）。
2. 继承 `SubAgent`，声明 `name` 与 `capabilities`，实现 `run(toolbox, ...)`。
3. 在 `OrchestratorAgent.run` 中为它构造 `ScopedToolbox` 并加入路由。
4. 在 `tests/test_multi_agent.py` 中补充权限与路由测试。

## 已知取舍

- 一次问答最多的大模型调用数为：`evaluator` 最多 `RAG_AGENT_MAX_ITERATIONS - 1` 次 + `answerer` 1 次。
  原单 Agent 版本每轮 1 次；多 Agent 版本的调用次数、延迟与准确率对比尚未做基准测试。
- `retriever` 目前不使用大模型，查询改写由 `evaluator` 给出。
