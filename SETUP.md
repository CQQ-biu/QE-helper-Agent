# 快速开始指南

## 前置要求

1. Python 3.8+ 
2. Node.js 16+
3. Docker（推荐，用于启动PostgreSQL/pgvector和Redis）

## 安装步骤

### 1. 后端安装

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建.env文件
# 方式1：从.env.example复制（推荐）
# Windows:
copy .env.example .env
# Linux/Mac:
cp .env.example .env

# 方式2：如果.env.example不存在，可以手动创建.env文件
# 文件内容参考README.md中的"配置说明"部分
```

### 2. 启动PostgreSQL/pgvector和Redis

```bash
# 在项目根目录执行
docker compose up -d postgres redis
```

如使用已有PostgreSQL实例，请先安装pgvector扩展，并在`backend/.env`中填写连接地址。

### 3. 启动后端服务

**Windows:**
```bash
# 方式1：使用批处理文件
start.bat

# 方式2：分别启动
# 终端1：
python run.py

# 终端2：
python run_celery.py
```

**Linux/Mac:**
```bash
# 方式1：使用脚本
chmod +x start.sh
./start.sh

# 方式2：分别启动
# 终端1：
python run.py

# 终端2：
celery -A app.services.task_service.celery_app worker --loglevel=info
```

### 4. 前端安装

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 访问应用

- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 验证安装

1. 访问 http://localhost:8000/health 应该返回 `{"status": "healthy"}`
2. 访问 http://localhost:8000/docs 查看API文档
3. 访问前端页面，填写信息并上传一个测试Excel文件

## 常见问题

### Redis连接失败
- 确保Redis服务正在运行
- 检查`backend/.env`中的Redis配置

### 端口被占用
- 修改`backend/run.py`中的端口号
- 修改`frontend/vite.config.js`中的端口号

### 数据库错误
- 确认PostgreSQL已安装pgvector，且`.env`中的`DATABASE_URL`为PostgreSQL连接串
- 应用首次启动会自动启用vector扩展并创建业务表和向量表

