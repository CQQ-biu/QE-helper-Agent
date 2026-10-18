from app.services.recursive_chunker import RecursiveSemanticChunker


def test_prefers_section_paragraph_and_sentence_boundaries():
    text = (
        "# 第一章 设备管理\n\n"
        "设备投入使用前应完成验收。设备应建立台账。\n\n"
        "校准周期为一年。出现异常时应立即复检。\n\n"
        "# 第二章 安全管理\n\n"
        "消防通道应保持畅通。严禁堆放物品。"
    )
    chunker = RecursiveSemanticChunker(chunk_size=24, chunk_overlap=6)

    chunks = chunker.split(text)

    assert len(chunks) > 1
    assert all(chunker.count_tokens(chunk) <= 24 for chunk in chunks)
    # 长章节拆开后，正文块仍携带章节标题，且正常句子保留句末标点。
    assert all(chunk.startswith("#") for chunk in chunks)
    assert all(chunk.endswith("。") for chunk in chunks)
    assert any(chunk.startswith("# 第二章 安全管理") for chunk in chunks)


def test_oversized_sentence_falls_back_to_token_window():
    text = " ".join(f"token{i}" for i in range(25))
    chunker = RecursiveSemanticChunker(chunk_size=10, chunk_overlap=2)

    chunks = chunker.split(text)

    assert len(chunks) == 3
    assert all(chunker.count_tokens(chunk) <= 10 for chunk in chunks)
    assert chunks[1].startswith("token8 token9")
    assert chunks[2].startswith("token16 token17")
