import json
from pathlib import Path
from types import SimpleNamespace

from app.services.rag_service import RAGService
from app.services.vector_store import VectorSearchResult


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.complete_calls = []

    def embed(self, texts, model):
        # 与“校准”有关的文本落到 x 轴，其余文本落到 y 轴。
        return [[1.0, 0.0] if "校准" in text else [0.0, 1.0] for text in texts]

    def complete(self, messages, model, temperature, tools=None, tool_choice=None):
        self.complete_calls.append({"messages": list(messages), "tool_choice": tool_choice})
        return next(self.responses)


class FakeVectorStore:
    def synchronize(self, files, chunk_loader):
        self.chunks = [
            (text, path.name) for path in files for text in chunk_loader(path)
        ]

    def has_chunks(self):
        return bool(getattr(self, "chunks", []))

    def search(self, query_vector, top_k, routed_source=None):
        if query_vector != [1.0, 0.0]:
            return []
        matches = [item for item in self.chunks if not routed_source or item[1] == routed_source]
        return [VectorSearchResult(text, source, 1.0) for text, source in matches[:top_k]]

    def source_exists(self, source):
        return any(item[1] == source for item in getattr(self, "chunks", []))


def tool_call(call_id, query):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": "search_knowledge", "arguments": json.dumps({"query": query}, ensure_ascii=False)},
        }],
    }


def make_settings(kb_dir: Path, threshold=0.35, max_iterations=3):
    return SimpleNamespace(
        RAG_KNOWLEDGE_BASE_DIR=str(kb_dir), RAG_EMBEDDING_MODEL="embedding-test",
        RAG_CHAT_MODEL="chat-test", RAG_TOP_K=2, RAG_SIMILARITY_THRESHOLD=threshold,
        RAG_CHUNK_SIZE=100, RAG_CHUNK_OVERLAP=10, RAG_EMBEDDING_BATCH_SIZE=10,
        RAG_TEMPERATURE=0.0, RAG_API_KEY="fake", RAG_BASE_URL="http://unused",
        RAG_REQUEST_TIMEOUT=1, RAG_AGENT_MAX_ITERATIONS=max_iterations,
        RAG_EMBEDDING_DIMENSIONS=2,
    )


def test_agent_rewrites_query_then_answers_from_evidence(tmp_path):
    (tmp_path / "quality.md").write_text("计量设备校准周期为一年。", encoding="utf-8")
    client = FakeClient([
        tool_call("call-1", "设备维护要求"),
        tool_call("call-2", "设备校准周期"),
        {"role": "assistant", "content": "设备应每年校准一次。"},
    ])
    service = RAGService(make_settings(tmp_path), client=client, vector_store=FakeVectorStore())

    result = service.answer("设备多久校准一次？", "简体中文")

    assert result.answer == "设备应每年校准一次。"
    assert result.similarity == 1.0
    assert result.sources == ["quality.md"]
    assert result.iterations == 3
    assert result.search_queries == ["设备维护要求", "设备校准周期"]
    assert client.complete_calls[0]["tool_choice"] == "required"
    second_observation = client.complete_calls[1]["messages"][-1]["content"]
    assert json.loads(second_observation)["found"] is False
    final_observation = client.complete_calls[2]["messages"][-1]["content"]
    assert "计量设备校准周期为一年" in final_observation


def test_agent_rejects_ungrounded_answer(tmp_path):
    (tmp_path / "quality.md").write_text("计量设备校准周期为一年。", encoding="utf-8")
    client = FakeClient([
        tool_call("call-1", "消防通道要求"),
        {"role": "assistant", "content": "消防通道宽度应为两米。"},
    ])
    service = RAGService(make_settings(tmp_path), client=client, vector_store=FakeVectorStore())

    assert service.answer("消防通道多宽？", "简体中文") is None


def test_agent_forces_final_answer_at_iteration_limit(tmp_path):
    (tmp_path / "quality.md").write_text("计量设备校准周期为一年。", encoding="utf-8")
    client = FakeClient([
        tool_call("call-1", "设备校准周期"),
        tool_call("call-2", "计量设备校准"),
        {"role": "assistant", "content": "设备应每年校准一次。"},
    ])
    service = RAGService(
        make_settings(tmp_path, max_iterations=2), client=client, vector_store=FakeVectorStore()
    )

    result = service.answer("设备多久校准一次？", "简体中文")

    assert result.answer == "设备应每年校准一次。"
    assert result.iterations == 2
    assert client.complete_calls[-1]["tool_choice"] == "none"
