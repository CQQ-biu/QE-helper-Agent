# 知识库使用说明

把质量标准、规范、FAQ 等资料放到 `backend/knowledge_base/`。支持 `.txt`、`.md`、`.csv`、`.json`、`.xlsx`、`.pdf` 和 `.docx`。

Celery Worker 会在首次处理问题时把文档分块和 embedding 写入 PostgreSQL/pgvector；知识文件新增、删除或修改后，下一次问答只更新变化的文件，无需重启。不要把说明性文件放入 `knowledge_base`，否则它也会作为知识参与检索。

文档会按“章节标题 → 段落 → 句子 → token”逐级递归切分。系统优先保留完整章节、段落和句子；只有单句仍超过大小限制时才按 token 滑窗切分。长章节拆分后会在子块中保留章节标题，避免正文失去上下文。

来源映射清单不要放在 `knowledge_base` 目录内，避免它本身被建立知识索引。可复制
`source_mapping.example.csv`，维护“关键词、文件名、优先级”后，通过
`RAG_SOURCE_MAPPING_FILE` 指向该文件。
