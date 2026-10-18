# QE Helper - Excel问答处理系统

一个基于FastAPI和Vue的Excel问答处理系统，可以自动解析Excel文件中的问题，生成答案并填入到Excel中，同时保持原有格式不变。

## 功能特性

1. **Excel上传与解析**
   - 支持上传Excel文件（.xlsx, .xls）
   - 自动解析Sheet和列信息
   - 支持多Sheet处理

2. **灵活的配置**
   - 用户可选择需要处理的Sheet
   - 自定义Score列和答案列
   - 支持跨多列的问题（如A到F列为一个问题）

3. **RAG答案生成与填入**
   - 从本地知识库进行向量检索，再由大模型严格依据命中资料生成答案
   - 分数由最高检索相似度按用户设置的最高分换算，不再随机生成
   - 支持 TXT、Markdown、CSV、JSON、Excel、PDF 和 Word 知识文件
   - 高亮显示填入的Score和答案单元格
   - 完全保留原有Excel格式和样式

4. **异步处理**
   - 使用Celery实现异步任务处理
   - 实时查询任务状态
   - 支持大文件处理

5. **数据持久化**
   - 保存用户填写的信息
   - 保存Excel文件到数据库
   - 记录完整的操作日志

6. **日志系统**
   - 文件日志和数据库日志双记录
   - 支持不同级别的日志记录

## 技术栈

### 后端
- **FastAPI**: 现代、快速的Web框架
- **SQLAlchemy**: ORM框架
- **Celery**: 异步任务队列
- **Redis**: Celery的消息代理
- **openpyxl**: Excel文件处理（保持格式）
- **PostgreSQL + pgvector**: 业务数据、知识分块和向量持久化，并在数据库内完成相似度检索

### 前端
- **Vue 3**: 渐进式JavaScript框架
- **Element Plus**: Vue 3组件库
- **Vite**: 快速的前端构建工具
- **Axios**: HTTP客户端

## 项目结构

```
qe-helper-main/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API路由
│   │   │   ├── upload.py   # 上传相关API
│   │   │   └── download.py # 下载相关API
│   │   ├── db/             # 数据库配置
│   │   │   └── database.py
│   │   ├── models.py       # 数据库模型
│   │   ├── schemas.py      # Pydantic模型
│   │   ├── services/       # 业务逻辑服务
│   │   │   ├── excel_service.py    # Excel处理服务
│   │   │   ├── rag_service.py      # RAG与Agent Loop
│   │   │   ├── vector_store.py     # pgvector索引同步与检索
│   │   │   └── task_service.py     # 异步任务服务
│   │   ├── utils/          # 工具类
│   │   │   └── logger.py   # 日志工具
│   │   ├── config.py       # 配置文件
│   │   └── main.py         # FastAPI主应用
│   ├── requirements.txt    # Python依赖
│   ├── run.py              # 启动脚本
│   └── run_celery.py       # Celery Worker启动脚本
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── views/         # 页面组件
│   │   │   └── Home.vue   # 主页面
│   │   ├── services/      # API服务
│   │   │   └── api.js
│   │   ├── router/        # 路由配置
│   │   │   └── index.js
│   │   ├── App.vue        # 根组件
│   │   └── main.js        # 入口文件
│   ├── package.json       # Node依赖
│   └── vite.config.js     # Vite配置
└── README.md              # 项目文档
```

## 安装与运行

### 1. 后端设置

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量文件
cp .env.example .env

# 编辑.env文件，配置数据库和Redis连接
```

### 2. 启动PostgreSQL/pgvector和Redis

```bash
# 在项目根目录启动开发环境依赖
docker compose up -d postgres redis
```

### 3. 启动后端服务

```bash
# 启动FastAPI服务器
python run.py

# 在另一个终端启动Celery Worker
python run_celery.py
# 或使用命令：
# celery -A app.services.task_service.celery_app worker --loglevel=info
```

后端服务默认运行在 `http://localhost:8000`

### 4. 前端设置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务默认运行在 `http://localhost:5173`

## 使用说明

1. **填写基本信息**
   - 客户名称、客户类型、工号、填表日期
   - 选择答案语言（简体中文/英语）
   - 设置最高分数

2. **上传Excel文件**
   - 点击"选择文件"选择Excel文件
   - 点击"上传并解析"按钮
   - 系统会自动解析Sheet和列信息

3. **配置Excel处理**
   - 为每个Sheet选择是否启用
   - 选择Score列（分数列）
   - 选择答案列（答案填入的位置）
   - 选择问题列（可以多选，支持跨多列）

4. **开始处理**
   - 点击"开始处理"按钮
   - 系统会异步处理Excel
   - 实时查看处理进度

5. **下载结果**
   - 处理完成后，点击"下载处理后的Excel"按钮
   - 下载的文件中，Score和答案单元格会高亮显示

## 数据库设计

### TaskRecord（任务记录表）
- 存储用户填写的基本信息
- 记录任务状态（pending/processing/completed/failed）

### ExcelFile（Excel文件表）
- 存储上传的Excel文件信息
- 保存处理后的文件路径
- 存储Excel配置信息（JSON格式）

### SystemLog（系统日志表）
- 记录所有操作日志
- 支持按任务ID查询日志

### KnowledgeDocument（知识文档表）
- 记录文件哈希、模型、向量维度和分块参数，用于识别新增、修改和删除的知识文件

### KnowledgeChunk（知识分块表）
- 保存分块正文和 `vector` 类型的 embedding
- 使用余弦距离 HNSW 索引执行 Top-K 近似向量检索

## 配置说明

### 后端配置（backend/.env）

```env
# 数据库配置
DATABASE_URL=postgresql+psycopg2://qe_helper:qe_helper@localhost:5432/qe_helper

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 文件路径配置
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
LOG_DIR=./logs

# 日志级别
LOG_LEVEL=INFO

# CORS配置
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

## RAG 知识库配置

1. 将质量标准、规范或 FAQ 放入 `backend/knowledge_base/`。
2. 复制 `backend/.env.example` 为 `backend/.env`，至少填写 `RAG_API_KEY`。
3. 默认使用 OpenAI API；也可以通过 `RAG_BASE_URL`、`RAG_CHAT_MODEL`、
   `RAG_EMBEDDING_MODEL` 接入同时提供 embeddings、chat completions 和 function/tool calling 的兼容服务。
4. 重启 FastAPI 与 Celery Worker。首次问答会把分块和 embedding 写入 PostgreSQL；后续只重建发生变化的文件，服务重启后可直接复用索引。

数据库启动时会自动执行 `CREATE EXTENSION IF NOT EXISTS vector` 并创建知识索引表。数据库用户
需要具备首次启用扩展的权限；生产环境也可以由 DBA 预先安装扩展。`RAG_EMBEDDING_DIMENSIONS`
必须与 embedding 模型的实际输出一致，默认 `text-embedding-3-small` 为 1536 维。
旧版 `qe_helper.db` 中的数据不会自动迁移；升级已有环境时需先备份，再通过迁移脚本或数据库
导入工具将业务表导入 PostgreSQL。知识向量无需迁移，系统会根据知识文件重新生成。

### 来源文件映射

如果业务已经维护“问题关键词 → 来源文件”的清单，可将清单配置为
`RAG_SOURCE_MAPPING_FILE`。支持 XLSX、CSV 和 JSON，建议使用列名 `关键词`、`文件名`、
`优先级`，示例见 `backend/source_mapping.example.csv`。一个单元格可使用 `|`、逗号或分号
填写多个关键词。问题命中规则后，Agent 的检索范围会锁定到指定知识文件，最终来源列也以
该规则文件名回填；未命中规则时仍使用普通向量检索得到的来源。

同一问题命中多条规则时，优先级数字大的规则优先；优先级相同时使用更长、更具体的关键词。
映射文件变更后会自动重新加载。映射中的文件名必须能匹配知识库中的相对路径或文件名，
否则系统不会拿其他文件冒充来源，而是按“未检索到”处理并记录日志。

处理流程为：加载知识文件 → 文本分块 → embedding 向量化并持久化到 pgvector → PostgreSQL 余弦相似度召回 Top-K
片段 → Agent 判断证据是否充分并按需改写查询继续检索 → 生成受知识约束的答案 → 回填原工作簿。最高相似度低于
`RAG_SIMILARITY_THRESHOLD`（默认 0.35）时，答案写入“未检索到”，避免模型猜测。

### Agent Loop

每个 Excel 问题现在由一个受控循环处理。第一轮强制调用 `search_knowledge` 工具；模型读取
工具观察结果后，可以结束并回答，也可以换一个更准确的查询继续搜索。达到
`RAG_AGENT_MAX_ITERATIONS` 后系统会禁用工具并强制生成最终结果，防止无限循环。系统还会在
代码层校验：没有任何达到相似度阈值的检索证据时，即使模型输出了答案也会丢弃并回填
“未检索到”。每次使用的查询、循环次数和知识来源都会写入任务日志。

Excel 配置中可选择“来源文件列”。系统会将业务映射确定的文件名写入该列；没有命中映射规则
时，写入实际召回的知识文件名。

主要参数：

- `RAG_TOP_K`：传给大模型的相关片段数。
- `RAG_EMBEDDING_DIMENSIONS`：向量列维度，必须与 embedding 接口输出一致；修改后需要执行数据库结构迁移或重建知识向量表。
- `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP`：分块大小和重叠大小（估算 token 数）。系统按 section → paragraph → sentence → token 递归切分，尽量保留完整语义单元。
- `RAG_SIMILARITY_THRESHOLD`：最低召回阈值；误答多时调高，漏答多时调低。
- `RAG_TEMPERATURE`：生成随机度，质量稽核建议保持接近 0。
- `RAG_AGENT_MAX_ITERATIONS`：单个问题最多允许的 Agent 决策/检索轮数，默认 3。

## API接口

### 上传Excel
- **POST** `/api/v1/upload`
- 上传Excel文件并解析

### 处理Excel
- **POST** `/api/v1/process`
- 根据配置处理Excel

### 查询任务状态
- **GET** `/api/v1/status/{task_id}`
- 查询任务处理状态

### 下载Excel
- **GET** `/api/v1/download/{task_id}`
- 下载处理后的Excel文件

## 注意事项

1. **Excel格式保持**
   - 使用`openpyxl`库可以最大程度保持Excel原有格式
   - 只修改指定单元格的值和背景色，不改变其他格式

2. **文件大小限制**
   - 默认最大文件大小为50MB
   - 可在配置文件中修改`MAX_FILE_SIZE`

3. **异步处理**
   - 大文件处理可能需要较长时间
   - 前端会每2秒自动查询任务状态

4. **数据库要求**
   - 项目统一使用 PostgreSQL，并依赖 pgvector 扩展；SQLite/MySQL 不支持当前向量表和检索表达式
   - `docker-compose.yml` 提供了可直接运行的本地 PostgreSQL/pgvector 环境

## 常见问题

### Q: Excel处理时格式丢失？
A: 确保使用`openpyxl`的`load_workbook`时不要使用`data_only=True`，这会丢失格式。

### Q: Celery任务不执行？
A: 检查Redis是否正常运行，以及Celery Worker是否已启动。

### Q: 前端无法连接后端？
A: 检查CORS配置，确保前端地址在`CORS_ORIGINS`中。

## 开发计划

- [ ] 支持更多Excel格式（.xls等）
- [ ] 添加用户认证和权限管理
- [ ] 支持批量处理多个Excel文件
- [ ] 添加处理历史记录查看
- [ ] 优化大文件处理性能
- [ ] 添加Excel模板验证功能

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！
