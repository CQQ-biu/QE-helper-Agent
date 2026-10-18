# 故障排查指南

## Celery Worker 没有运行

### 问题现象
- 任务状态一直停留在 `pending`
- 后端日志显示任务已提交，但任务没有执行

### 解决方法

**1. 确认需要运行两个终端：**
- 终端1: 运行 FastAPI (`python run.py`)
- 终端2: 运行 Celery Worker (`python run_celery.py`)

**2. 启动 Celery Worker：**
```bash
cd backend
# 确保在虚拟环境中
python run_celery.py
```

**3. 验证 Worker 是否运行：**
```bash
python check_celery.py
```

应该看到：
```
✓ 发现 1 个活动的Worker
```

**4. Worker 正常运行时的输出示例：**
```
[2024-01-01 12:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2024-01-01 12:00:00,100: INFO/MainProcess] mingle: searching for neighbors
[2024-01-01 12:00:00,200: INFO/MainProcess] mingle: all alone
[2024-01-01 12:00:00,300: INFO/MainProcess] celery@DESKTOP-8900SMG ready.
```

当任务执行时，会看到：
```
[2024-01-01 12:00:00,000: INFO/MainProcess] Received task: process_excel_task[xxx]
[2024-01-01 12:00:00,100: INFO/ForkPoolWorker-1] Task process_excel_task[xxx] started
...
[2024-01-01 12:00:10,000: INFO/ForkPoolWorker-1] Task process_excel_task[xxx] succeeded
```

## 查看任务状态

### 方法1: 使用脚本查看
```bash
cd backend

# 列出所有任务
python check_task_status.py

# 查看指定任务详情
python check_task_status.py <task_id>
```

### 方法2: 直接查看数据库（PostgreSQL）
```bash
# 进入docker compose中的PostgreSQL
cd ..
docker compose exec postgres psql -U qe_helper -d qe_helper

SELECT task_id, status, customer_name, created_at, updated_at 
FROM task_records 
ORDER BY created_at DESC 
LIMIT 10;

# 查看日志
SELECT * FROM system_logs 
WHERE task_id = '<your_task_id>' 
ORDER BY created_at DESC;

\q
```

## 常见问题

### 1. Redis 连接失败
**错误信息：** `Connection refused` 或 `redis.exceptions.ConnectionError`

**解决：**
- 确保 Redis 服务正在运行
- 检查 Redis 配置（`backend/.env` 或 `backend/app/config.py`）

### 2. 任务一直 pending
**可能原因：**
- Celery Worker 没有运行（最常见）
- Redis 连接问题
- 任务参数错误导致 Worker 执行失败

**排查步骤：**
1. 运行 `python check_celery.py` 检查 Worker
2. 查看 Celery Worker 终端的错误信息
3. 查看日志文件：`backend/logs/app_*.log`

### 3. 任务执行失败但没有更新状态
**检查：**
- Celery Worker 终端的错误堆栈
- 数据库日志表：`system_logs`
- 日志文件：`backend/logs/app_*.log`

## 日志位置

1. **文件日志：** `backend/logs/app_YYYYMMDD.log`
2. **数据库日志：** `system_logs` 表
3. **Celery Worker 终端输出**

## 调试技巧

### 启用详细日志
在 `backend/app/config.py` 中修改：
```python
LOG_LEVEL = "DEBUG"  # 改为 DEBUG 查看更详细的日志
```

### 检查任务是否正确提交
查看后端终端，应该看到：
```
INFO: 任务已提交到Celery，任务ID: <celery_task_id>, task_id: <your_task_id>
```

### 检查 Worker 是否收到任务
在 Celery Worker 终端应该看到：
```
[INFO] Received task: process_excel_task[<celery_task_id>]
```

