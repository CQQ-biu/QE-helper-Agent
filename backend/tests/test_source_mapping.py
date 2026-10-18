import json
from pathlib import Path
from types import SimpleNamespace

from app.services.rag_service import RAGService
from app.services.source_mapping import SourceMappingResolver
from app.services.vector_store import VectorSearchResult


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.complete_calls = []

    def embed(self, texts, model):
        return [[1.0, 0.0] if "校准" in text else [0.0, 1.0] for text in texts]

    def complete(self, messages, model, temperature, tools=None, tool_choice=None):
        self.complete_calls.append(list(messages))
        return next(self.responses)


class FakeVectorStore:
    def synchronize(self, files, chunk_loader):
        self.chunks = [(text, path.name) for path in files for text in chunk_loader(path)]

    def has_chunks(self):
        return bool(self.chunks)

    def search(self, query_vector, top_k, routed_source=None):
        matches = [item for item in self.chunks if not routed_source or item[1] == routed_source]
        return [VectorSearchResult(text, source, 1.0) for text, source in matches[:top_k]]

    def source_exists(self, source):
        return any(item[1] == source for item in self.chunks)


def tool_call(query):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "arguments": json.dumps({"query": query}, ensure_ascii=False),
            },
        }],
    }


def make_settings(kb_dir: Path, mapping_file: Path):
    return SimpleNamespace(
        RAG_KNOWLEDGE_BASE_DIR=str(kb_dir), RAG_SOURCE_MAPPING_FILE=str(mapping_file),
        RAG_EMBEDDING_MODEL="embedding-test", RAG_CHAT_MODEL="chat-test", RAG_TOP_K=2,
        RAG_SIMILARITY_THRESHOLD=0.35, RAG_CHUNK_SIZE=100, RAG_CHUNK_OVERLAP=10,
        RAG_EMBEDDING_BATCH_SIZE=10, RAG_TEMPERATURE=0.0, RAG_API_KEY="fake",
        RAG_BASE_URL="http://unused", RAG_REQUEST_TIMEOUT=1, RAG_AGENT_MAX_ITERATIONS=3,
        RAG_EMBEDDING_DIMENSIONS=2,
    )


def test_longer_keyword_wins_when_priority_is_equal(tmp_path):
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "关键词,文件名,优先级\n设备,通用设备规范.md,0\n设备校准,计量规范.md,0\n",
        encoding="utf-8-sig",
    )

    rule = SourceMappingResolver(mapping).resolve("请说明设备校准周期")

    assert rule.keyword == "设备校准"
    assert rule.source == "计量规范.md"


def test_agent_search_is_limited_to_mapped_source(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    (kb_dir / "计量规范.md").write_text("设备校准周期为一年。", encoding="utf-8")
    (kb_dir / "其他规范.md").write_text("设备校准周期为两年。", encoding="utf-8")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("关键词,文件名\n设备校准,计量规范.md\n", encoding="utf-8-sig")
    client = FakeClient([
        tool_call("设备校准周期"),
        {"role": "assistant", "content": "设备应每年校准一次。"},
    ])
    service = RAGService(
        make_settings(kb_dir, mapping), client=client, vector_store=FakeVectorStore()
    )

    result = service.answer("设备校准周期是多少？", "简体中文")

    assert result.answer == "设备应每年校准一次。"
    assert result.sources == ["计量规范.md"]
    assert result.source_rule_keyword == "设备校准"
    observation = json.loads(client.complete_calls[-1][-1]["content"])
    assert observation["routed_by_keyword"] == "设备校准"
    assert {match["indexed_source"] for match in observation["matches"]} == {"计量规范.md"}
